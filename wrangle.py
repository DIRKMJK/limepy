"""Process and summarise data from LimeSurvey survey."""

from collections import OrderedDict
import re
import pandas as pd
import numpy as np
import xmltodict

QUESTION_TYPES = {
    'F': 'Array',
    'B': 'Array (10 point choice)',
    ':': 'Array (Numbers)',
    ';': 'Array (Texts)',
    '1': 'Array dual scale',
    'D': 'Date / time',
    'K': 'Multiple numerical',
    'R': 'Ranking',
    'P': 'Multiple choice with comments',
    'L': 'List radio',
    '!': 'List dropdown',
    '5': 'Five point choice',
    'M': 'Multiple choice',
    'O': 'List with comment',
    'T': 'Long free text',
    'S': 'Short free text',
    'X': 'Text display',
    'N': 'Numerical input',
    'P': 'Multiple choice with comments'
}


class Survey():
    """Contains the structure and data of a LimeSurvey survey."""

    def __init__(self, dataframe, structure):
        """

        :param dataframe: dataframe containing the survey export,
            heading type must be 'code'
        :param survey_structure: survey structure, exported as .lss file

        """
        self.dataframe = dataframe
        self.questions, self.groups = self.parse_structure(structure)
        self.question_list = self.create_question_list()
        self.readable_df = self.readable_df()

    def get_question_type(self, question_type_code):
        """Return the name of the question type"""

        if question_type_code in QUESTION_TYPES:
            return QUESTION_TYPES[question_type_code]
        return question_type_code

    def get_columns(self, question):
        """Identify column names associated with question."""

        title = question['title']
        indices = [i for i, c in enumerate(self.dataframe.columns)
                   if c.split('[')[0] == title]
        if not indices:
            indices = [-99, -99]
        return min(indices), len(indices)

    def parse_structure(self, structure):
        """Parse the structure of the survey."""

        if isinstance(structure, str):
            structure = xmltodict.parse(structure)
        document = structure['document']
        groups = OrderedDict()
        questions = OrderedDict()
        start_columns = []
        if isinstance(document['groups']['rows']['row'], list):
            for group in document['groups']['rows']['row']:
                groups[group['gid']] = group
        else:
            group = document['groups']['rows']['row']
            groups[group['gid']] = group
        for question in document['questions']['rows']['row']:
            qid = question['qid']
            gid = question['gid']
            question['question_type'] = self.get_question_type(question['type'])
            start, length = self.get_columns(question)
            question['columns'] = start, length
            start_columns.append(start)
            questions[qid] = question
            if 'questions' not in groups[gid]:
                groups[gid]['questions'] = []
            groups[gid]['questions'].append(qid)
        if 'answers' in document.keys():
            for answer in document['answers']['rows']['row']:
                qid = answer['qid']
                scale = answer['scale_id']
                if 'answers' not in questions[qid]:
                    questions[qid]['answers'] = {}
                if scale not in questions[qid]['answers']:
                    questions[qid]['answers'][scale] = []
                questions[qid]['answers'][scale].append(answer)
        if 'subquestions' in document.keys():
            for subquestion in document['subquestions']['rows']['row']:
                parent_qid = subquestion['parent_qid']
                scale = subquestion['scale_id']
                if 'subquestions' not in questions[parent_qid]:
                    questions[parent_qid]['subquestions'] = {}
                if scale not in questions[parent_qid]['subquestions']:
                    questions[parent_qid]['subquestions'][scale] = []
                questions[parent_qid]['subquestions'][scale].append(subquestion)
        if 'question_attributes' in document.keys():
            for attribute in document['question_attributes']['rows']['row']:
                if isinstance(attribute, dict):
                    qid = attribute['qid']
                    if 'attributes' not in questions[qid]:
                        questions[qid]['attributes'] = []
                    questions[qid]['attributes'].append(attribute)
                    if (attribute['attribute'] == 'multiflexible_checkbox'
                            and attribute['value'] == '1'):
                        question_type = 'Array (Numbers) Checkbox layout'
                        questions[qid]['question_type'] = question_type
        start_columns = sorted(start_columns)
        for qid, question in questions.items():
            position = float(start_columns.index(question['columns'][0]))
            questions[qid]['position'] = position
        return questions, groups

    def create_question_list(self):
        """Create table of questions with metadata"""

        question_list = pd.DataFrame()
        for qid, question in self.questions.items():
            question_list.loc[qid, 'question'] = question['question']
            question_list.loc[qid, 'question_type'] = question['question_type']
            question_list.loc[qid, 'help'] = question['help']
            question_list.loc[qid, 'position'] = question['position']
            start, nr_columns = question['columns']
            question_list.loc[qid, 'start'] = int(start)
            question_list.loc[qid, 'nr_columns'] = int(nr_columns)
            group_name = self.groups[question['gid']]['group_name']
            question_list.loc[qid, 'group'] = group_name
            question_list.loc[qid, 'mandatory'] = question['mandatory']
            question_list.loc[qid, 'other'] = question['other']
        return question_list.sort_values(by='position')

    def code_to_answer(self, value, mapping):
        """Replace answer code with answer"""
        if pd.isnull(value):
            return None
        if value in mapping:
            return mapping[value]
        return value

    def readable_df(self):
        readable_df = self.dataframe.copy()
        """Create dataframe with readable colnames and values"""
        colnames = list(self.dataframe.columns)
        for qid, question in self.questions.items():
            start, nr_columns = question['columns']
            mapping = {}
            if 'answers' in question:
                for scale in question['answers']:
                    for answer in question['answers'][scale]:
                        mapping[answer['code']] = answer['answer']
            for i in range(start, start + nr_columns):
                colname = colnames[i]
                colname = colname.replace('\n', ' ')
                parts = re.match('(.*?)\[(.*)\]$', colname)
                if parts:
                    last = parts.groups()[-1]
                    if 'subquestions' in question:
                        for scale in question['subquestions']:
                            for sq in question['subquestions'][scale]:
                                last = last.replace(sq['title'], sq['question'])
                    colname = f'{question["question"]}[{last}]'
                else:
                    colname = question['question']
                colnames[i] = colname
                if mapping:
                    readable_df.iloc[:, i] = readable_df.iloc[:, i].map(lambda x: self.code_to_answer(x, mapping))

        readable_df.columns = colnames
        return readable_df

    def get_answer(self, question, answer_code):
        """Look up the answer beloning to an answer code."""

        for scale in question['answers']:
            for answer in question['answers'][scale]:
                if answer['code'] == answer_code:
                    return answer['answer']
        return answer_code

    def recode_checkbox(self, value):
        """
        Return 'N' if answer is missing, else 'Y'

        :param value: value

        """

        if pd.isnull(value):
            return "N"
        return "Y"

    def respondent(self, respondent_id, strip_tags=True, ignore=['X']):
        """Printable list of the answers of an individual respondent

        :param respondent_id: row index of the respondent
        :param strip_tags:  if True, remove html tags (Default value = True)
        :param ignore:  question types to be skipped (Default value = ['X'])

        """

        current_group_id = ''
        respondent = f'Respondent ID: {respondent_id}\n\n'
        for qid in self.question_list.index:
            question = self.questions[qid]
            if question['type'] in ignore:
                continue
            if question['gid'] != current_group_id:
                group_title = self.groups[question['gid']]['group_name'].upper()
                respondent += group_title + '\n\n'
                current_group_id = question['gid']
            respondent += question['question'] + '\n'

            # List (radio, dropdown)
            if question['type'] in ['!', 'L', 'O']:
                colname = question['title']
                value = self.dataframe.loc[respondent_id, colname]
                value = self.get_answer(question, value)
                respondent += f'- {value}\n'
                if question['other'] == 'Y':
                    colname = f"{question['title']}[other]"
                    value = self.dataframe.loc[respondent_id, colname]
                    if pd.notnull(value):
                        respondent += f"- Other: {value}\n"
                respondent += '\n'

            # Other single-column question
            elif question['title'] in self.dataframe.columns:
                value = self.dataframe.loc[respondent_id, question['title']]
                respondent += f"- {value}\n"
                if question['other'] == 'Y':
                    colname = f"{question['title']}[other]"
                    value = self.dataframe.loc[respondent_id, colname]
                    if pd.notnull(value):
                        respondent += f"- Other: {value}\n"
                respondent += '\n'

            # Multiple choice
            elif question['type'] in ['M', 'P']:
                for subquestion in question['subquestions']['0']:
                    colname = f"{question['title']}[{subquestion['title']}]"
                    value = self.dataframe.loc[respondent_id, colname]
                    value = self.recode_checkbox(value)
                    label = subquestion['question']
                    respondent += f"- {label}: {value}\n"
                if question['other'] == 'Y':
                    colname = f"{question['title']}[other]"
                    value = self.dataframe.loc[respondent_id, colname]
                    if pd.notnull(value):
                        respondent += f"- Other: {value}\n"
                respondent += '\n'

            # Array
            elif question['type'] in ['F']:
                for subquestion in question['subquestions']['0']:
                    colname = f"{question['title']}[{subquestion['title']}]"
                    label = subquestion['question']
                    value = self.dataframe.loc[respondent_id, colname]
                    value = self.get_answer(question, value)
                    respondent += f"- {label}: {value}\n"
                respondent += '\n'

            # Array (Numbers) or Checkbox Array
            elif question['type'] in [':', ';']:
                checkbox = (question['question_type']
                            == 'Array (Numbers) Checkbox layout')
                for subquestion_0 in question['subquestions']['0']:
                    label_0 = subquestion_0['question']
                    for subquestion_1 in question['subquestions']['1']:
                        label_1 = subquestion_1['question']
                        colname = (f"{question['title']}"
                                   f"[{subquestion_0['title']}"
                                   f"_{subquestion_1['title']}]")
                        value = self.dataframe.loc[respondent_id, colname]
                        if checkbox:
                            value = self.recode_checkbox(value)
                        respondent += f"- {label_0}, {label_1}: {value}\n"
                respondent += '\n'

            # Multiple numerical
            elif question['type'] in ['K']:
                for subquestion in question['subquestions']['0']:
                    colname = f"{question['title']}[{subquestion['title']}]"
                    value = self.dataframe.loc[respondent_id, colname]
                    label = subquestion['question']
                    respondent += f"- {label}: {value}\n"
                if question['other'] == 'Y':
                    colname = f"{question['title']}[other]"
                    value = self.dataframe.loc[respondent_id, colname]
                    respondent += f"- Other: {value}\n"
                respondent += '\n'

            # Ranking
            elif question['type'] == 'R':
                answers = question['answers']['0']
                for i in range(len(answers)):
                    colname = f"{question['title']}[{i + 1}]"
                    answer_code = self.dataframe.loc[respondent_id, colname]
                    value = self.get_answer(question, answer_code)
                    respondent += f"- {i + 1}: {value}\n"
                respondent += '\n'

            # Not implemented
            else:
                respondent += "Question type not implemented\n\n"

        if strip_tags:
            respondent = re.sub('<[^<]+?>', '', respondent)
        return respondent

    def __repr__(self):
        return f'<{self.__class__.__name__} object>'


class Question():
    """Metadata and answers of a LimeSurvey question"""

    def __init__(self, survey, qid, mask=None, method=None):
        """

        :param survey: object of Survey class
        :param qid: question id (see question_list)
        :param mask: list or series of booleans to create subset,
            if only subset of dataframe is to be summarised
        :param method: method for calculating average (mean or median)

        """
        self.survey = survey
        self.mask = mask
        self.subset = self.create_subset(survey.dataframe)
        self.metadata = survey.questions[str(int(qid))]
        self.question = self.metadata['question']
        self.type = self.metadata['type']
        self.method = method
        self.help = self.metadata['help']
        self.summary, self.valid = self.summarise()

    def create_subset(self, dataframe):
        """Create subset to be used for summarising data."""

        if self.mask is not None:
            return dataframe[self.mask]
        return dataframe

    def percentage_added(self, table, ntotal, nvalid):

        """Add column Percent and Valid Percent to value counts table."""

        table['Percent'] = round(100 * table['Count'] / ntotal, 1)
        table['Valid Percent'] = round(100 * table['Count'] / nvalid, 1)
        return table

    def summarise(self):
        """Summarise answers to question"""

        summary = pd.DataFrame()
        valid = []

        # Numerical input
        if self.type in ['N']:
            colname = self.metadata['title']
            descriptives = self.subset[colname].describe()
            summary = pd.DataFrame(descriptives)

        # List (radio, dropdown, ...)
        if self.type in ['!', 'L', 'O', '5']:
            colname = self.metadata['title']
            values = self.subset[colname]
            valid = [i for i, v in enumerate(values) if pd.notnull(v)]
            if self.type == '5':
                answers = [{'answer': a, 'code': a} for a in range(1, 6)]
            else:
                answers = self.metadata['answers']['0']
            for answer in answers:
                count = list(values).count(answer['code'])
                summary.loc[answer['answer'], 'Count'] = count
            if self.metadata['other'] == 'Y':
                colname = f"{self.metadata['title']}[other]"
                other = [i for i, v in enumerate(self.subset[colname])
                         if pd.notnull(v)]
                summary.loc['Other', 'Count'] = len(other)
                valid.extend(other)

        # Multiple Choice
        if self.type in ['M', 'P']:
            for subquestion in self.metadata['subquestions']['0']:
                colname = f"{self.metadata['title']}[{subquestion['title']}]"
                values = [pd.notnull(v) for v in self.subset[colname]]
                label = subquestion['question']
                summary.loc[label, 'Count'] = sum(values)
                valid.extend([i for i, v in enumerate(values) if v == 1])
            if self.metadata['other'] == 'Y':
                colname = f"{self.metadata['title']}[other]"
                other = [i for i, v in enumerate(self.subset[colname])
                         if pd.notnull(v)]
                summary.loc['Other', 'Count'] = len(other)
                valid.extend(other)

        # Array
        if self.type == 'F':
            for subquestion in self.metadata['subquestions']['0']:
                colname = f"{self.metadata['title']}[{subquestion['title']}]"
                values = self.subset[colname]
                valid.extend([i for i, v in enumerate(values)
                              if pd.notnull(v)])
                sq_label = subquestion['question']
                for answer in self.metadata['answers']['0']:
                    count = list(values).count(answer['code'])
                    answer_label = answer['answer']
                    summary.loc[sq_label, answer_label] = count

        # Multiple numerical
        if self.type in ['K']:
            for subquestion in self.metadata['subquestions']['0']:
                label = subquestion['question']
                colname = f"{self.metadata['title']}[{subquestion['title']}]"
                values = self.subset[colname]
                valid.extend([i for i, v in enumerate(values)
                              if pd.notnull(v)])
                valid_values = [v for v in values if pd.notnull(v)]
                summary.loc[label, 'mean'] = np.mean(valid_values)
                summary.loc[label, 'median'] = np.median(valid_values)

        # Array (Numbers) or Checkbox Array
        if self.type in [':']:
            checkbox = (self.metadata['question_type']
                        == 'Array (Numbers) Checkbox layout')
            if not checkbox and (not self.method
                                 or self.method not in ['mean', 'median']):
                raise ValueError('Specify method (must be mean or median)')
            for subquestion_0 in self.metadata['subquestions']['0']:
                label_0 = subquestion_0['question']
                for subquestion_1 in self.metadata['subquestions']['1']:
                    label_1 = subquestion_1['question']
                    colname = (f"{self.metadata['title']}"
                               f"[{subquestion_0['title']}"
                               f"_{subquestion_1['title']}]")
                    values = self.subset[colname]
                    valid.extend([i for i, v in enumerate(values)
                                  if pd.notnull(v)])
                    if checkbox:
                        value = sum((v == 1) for v in values)
                    else:
                        valid_values = [float(v) for v in values
                                        if pd.notnull(v)]
                        if self.method == 'mean':
                            value = np.mean(valid_values)
                        if self.method == 'median':
                            value = np.median(valid_values)
                    summary.loc[label_0, label_1] = value

        # Ranking
        if self.type == 'R':
            answers = self.metadata['answers']['0']
            points = len(answers)
            for i in range(len(answers)):
                colname = f"{self.metadata['title']}[{i + 1}]"
                values = self.subset[colname]
                if i == 0:
                    valid = [i for i, v in enumerate(values) if pd.notnull(v)]
                for answer in answers:
                    score = (points * list(values).count(answer['code'])
                             / len(valid))
                    try:
                        summary.loc[answer['answer'], 'Points'] += score
                    except KeyError:
                        summary.loc[answer['answer'], 'Points'] = score
                points -= 1
            summary = summary.sort_values(by='Points', ascending=False)

        # Any other question type: return columns related to question
        if summary.empty:
            colnames = [c for c in self.subset.columns
                        if c.split('[')[0] == self.metadata['title']]
            for colname in colnames:
                valid.extend([i for i, v in enumerate(self.subset[colname])
                              if pd.notnull(v)])
            summary = self.subset[colnames]

        valid = set(valid)
        if self.type in ['M', 'L', '!', 'O', '5', 'P']:
            ntotal = len(self.subset)
            nvalid = len(valid)
            summary = self.percentage_added(summary, ntotal, nvalid)
        return summary, valid

    def write_open_ended(self, background_column_indices=None,
                         column_indices=None):
        """List the answers to an open-ended question

        :param background_column_indices: indices of columns containing
            background information to be included (Default value = None)
        :param column_indices: indices of columns to be used
            (Default value = None)

        """

        if not column_indices:
            start, length = self.metadata['columns']
            column_indices = range(start, start + length)
            if self.metadata['other'] == 'Y':
                column_indices = [
                    i for i in column_indices if
                    'other' in self.subset.columns[i] or
                    'comment' in self.subset.columns[i]
                    ]
        if (background_column_indices
                and not isinstance(background_column_indices, list)):
            background_column_indices = [background_column_indices]

        text = f'{self.question.upper()}\n'
        help_txt = self.metadata['help']
        if pd.notnull(help_txt):
            text += f'{help_txt}\n'
        text += '\n'

        for respondent in self.subset.index:
            respondent_txt = f'R{respondent}\n'
            include_respondent = False
            for col_index in column_indices:
                colname = self.subset.columns[col_index]
                value = self.subset.loc[respondent, colname]
                if pd.notnull(value):
                    respondent_txt += f'{value}\n'
                    include_respondent = True
            if include_respondent and background_column_indices:
                for col_index in background_column_indices:
                    colname = self.subset.columns[col_index]
                    value = self.subset.loc[respondent, colname]
                    for bg_qid, row in self.survey.question_list.iterrows():
                        if (row.start + row.nr_columns) > col_index:
                            bg_question = Question(self.survey, bg_qid)
                            bg_metadata = bg_question.metadata
                            break
                    if 'answers' in bg_metadata:
                        for scale in bg_metadata['answers']:
                            for answer in bg_metadata['answers'][scale]:
                                if answer['code'] == value:
                                    value = answer['answer']
                                    break
                    respondent_txt += f"- {value}\n"
            if include_respondent:
                text += respondent_txt + '\n\n'
        return text

    def __repr__(self):
        return f'<{self.__class__.__name__} object>'
