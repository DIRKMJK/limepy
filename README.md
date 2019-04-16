[LimeSurvey][limesurvey] is open-source survey software. Using pandas, the limepy package simplifies a number of tasks when working with LimeSurvey data:

- Downloading survey data. This requires that LimeSurvey’s RemoteControl 2 API is enabled, as explained [here][LSRC2].
- Creating a list of al the questions in the survey, with metadata.
- Summarising data, e.g. creating value counts for multi-column items such as multiple-choice questions; calculating averages for number arrays; or creating scores for a ranking question.
- Printing answers to open-ended questions.
- Printing the answers of an individual respondent.

Note that limepy uses f-strings and therefore requires Python 3.6 or higher.

Use at your own risk and please make sure to check the results.

# How is it different

There are various python packages for managing the LimeSurvey RemoteControl 2 API. While limepy can help you download survey data, the emphasis is on processing and summarising the data.

# Examples

## Download survey data

You can download survey data with the RemoteControl 2 API (provided the api is enabled in your LimeSurvey installation).

For a one-off download, you can of course do this manually. However, you may want to use the api if you want to write a preliminary report based on the first responses, and then automatically update it as new responses come in.

```python
from pathlib import Path
from limepy import download

csv = download.get_responses(base_url, user_name, password, user_id, sid)
path = Path('../data/data.csv')
path.write_text(csv)
```

## Create Survey object

A Survey object contains the data and metadata of a survey. To create a Survey object, you need:

- A csv containing the survey results. You can download it manually or use the api as described above. Make sure to set heading type to 'code' and reponse type to 'short'.
- An .lss file containing the survey structure. You can download this manually.

```python
from limepy.wrangle import Survey, Question
import pandas as pd

df = pd.read_csv('../data/data.csv', sep=';')
my_structure = open('../data/structure.lss').read()

my_survey = Survey(df, my_structure)
```

Note: if you use a merged dataframe (for example, data from various versions of the same questionnaire), you should reset the index before creating a Survey object.

## Get list of questions with metadata

```python
my_survey.question_list
```

## Print results for individual respondent

The `respondent` method will return a string listing the answers of an individual respondent. You need the respondent’s row index.

```python
my_survey.respondent(26)
```

## Create a readable dataframe

Create a dataframe with full questions as column names and ‘long’ responses as values.

```python
my_survey.readable_df
```

## Create a Question object

A Question object can be used to summarise data. To create a Question oject, you need a Survey object and the question id (find it in the index of the question list).

```python
my_question = Question(my_survey, 3154)
```

If you want to use a subset of the respondents for your analysis (e.g., exclude respondents that do not meet certain criteria, or drop duplicates), the most practical approach is probably to create a subset first and use that to create your Survey object. However, you can also use a mask if you want to create a Question object for a subset of the respondents.

```python
my_question = Question(my_survey, 3154, mask=pd.notnull(df.iloc[:, 8]))
```

## Summarise answers to a question

For many question types, limepy can summarise the results. 
- In many cases, this will return a dataframe containing value counts (as well as Percent and Valid Percent). 
- In case of a Numerical input question, the output will be a dataframe containing the results of the pandas DataFrame `describe` method. 
- In case of a Numbers array question, the average will be calculated for each option (but you must specify the method, i.e. 'mean' or 'median'). 
- In case of a Ranking question, the result will be a dataframe with scores calculated for each item. 
- If no method has been implemented for a question type, a dataframe will be returned which contains the columns associated with the question.

```python
my_question.summary
```

To show the metadata associated with a question:

```python
my_question.metadata
```

## Write answers to an open-ended question

The `write_open_ended` method creates a string listing all the answers to the question. Optionally, you can specify a list of indices of columns that contain background information you want included in the output.

```python
my_question.write_open_ended(background_column_indices=[9])
```

You can also create a folder and store text files containing the answers to all open-ended questions in the survey.

```python
from pathlib import Path

remove = ' _?:/()'

def include(row):
    for string in ['free text', 'comment']:
        if string in row.question_type:
            return True
    if row.other == 'Y':
        return True
    return False

for qid, row in my_survey.question_list.iterrows():
    if include(row):
        question = row.question
        for char in remove:
            question = question.replace(char, ' ')
        question = question[:25]
        path = Path('../data/open_ended') / f'{qid} {question}.md'
        path.write_text(Question(sv, qid).write_open_ended(background_column_indices=[9]))
```

## Create report as html

```python
def add_table(question, question_text=None):
    """Add table summarising question"""
    
    if not question_text:
        question_text = question.question
    html = f"<div class='tableHeader'>{question_text}</div>\n"
    html += question.summary.to_html() + '\n'
    help_txt = question.metadata['help']
    if help_txt:
        html += f"<div class='tableCaption'>{help_txt}</div>"
    return html


html = """<head>
<title>Title</title>
<link rel="stylesheet" href="styles.css">
<meta charset="utf-8">
</head>
<body>
"""

my_question = Question(my_survey, 44)
html += add_table(my_question)

html += "</body>"
```

[limesurvey]:https://en.wikipedia.org/wiki/LimeSurvey
[LSRC2]:https://manual.limesurvey.org/RemoteControl_2_API