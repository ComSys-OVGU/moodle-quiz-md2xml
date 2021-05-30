# Moodle Quiz - Markdown to XML

Tool to **convert strictly formatted Markdown files to Moodle's XML format**
which can be imported easily. It comes with its **own "meta syntax"** using existing Markdown constructs.

While there are other more complete and complex solutions like the
[GIFT format](https://docs.moodle.org/311/en/GIFT_format), this tool's syntax is designed to be simpler and straight
forward, maintaining readability and being renderable by Markdown renderers.

## Usage

1. clone Git repo

```shell
git clone https://github.com/ComSys-OVGU/moodle-quiz-md2xml.git
cd moodle-quiz-md2xml
```

### As Installed Package

2. run install script (also used to update)

```shell
pip3 install .
```

3. process your Markdown file(s)

```shell
moodle-md2xml foo.md bar.md
# will write foo.xml and bar.xml when no error occurred
```

### Use Code Directly

2. install dependencies

```shell
pip3 install -r requirements.txt
```

3. run `cli.py`

```shell
python3 moodle_quiz_md2xml/cli.py foo.md bar.md
# will write foo.xml and bar.xml when no error occurred
```

---

```
usage: moodle-md2xml [-h] [--config CONFIG_FILE] [--tags TAGS]
                     [--shuffle SHUFFLE_ANSWERS]
                     [--numbering {abc,ABC,123,iii,III}] [--verbose]
                     INPUT_FILE [INPUT_FILE ...]

Converts specially formatted Markdown files containing quiz questions to
Moodle's quiz XML format

positional arguments:
  INPUT_FILE            Markdown files to convert, wildcards are allowed

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG_FILE, -c CONFIG_FILE
                        configuration file (if not set: using default.ini)
  --tags TAGS, -t TAGS  comma-separated list of tags that shall always be
                        added to questions
  --shuffle SHUFFLE_ANSWERS, -s SHUFFLE_ANSWERS
                        shuffle answers by default (does not apply to
                        enumeration matching questions)
  --numbering {abc,ABC,123,iii,III}, -n {abc,ABC,123,iii,III}
                        default numbering scheme for single / multiple choice
                        questions
  --verbose, -v         enable some verbose / debug output
```

If you want to use your own configuration file, just copy the `default.ini` in the package directory
`moodle_quiz_md2xml` and change it to your needs.

## Syntax

The syntax is based on [CommonMark specification](https://spec.commonmark.org/). Every **question** consists of
**at least one paragraph** that will be used as the question's text / description and **exactly one list** which defines
the answers. How the list is structured defines to which Moodle question format
it will be converted to.

Between the paragraph and the list, there can be more paragraphs and code blocks that will just be added to the question
description / text. But keep in mind that a question always needs to start with a paragraph, and there may only be one
list for a single question.

Headings of level 1 (`# Heading 1`) optionally are used to group questions together. The text of the heading is
separated into parts by comma, and those parts will result in corresponding tags for the following questions until a new
heading is reached. 

Subheadings of level 2 (`## Heading 2`) optionally define question names explicitly (with 'names' meaning the identifier
displayed in Moodle), otherwise a name will be derived automatically from the question description / text. 

### Example / Question Types

````markdown
# Group 1, easy

## 1. Single Choice

What is the first answer?

- [x] Answer 1
- [ ] Answer 2
- [ ] Answer 3

## 2. Multiple Choice

What are your favourite programming languages? <!-- @shuffle=false @numbering=123 -->

- [x] **Python** (not the snake)
- [x] **C++** ("C with Classes")
- [ ] **PHP** (Hypertext Preprocessor)

# Group 1, intermediate

## 3. Enumerated Matching

Order the layers of the ISO/OSI model:

1. Physical Layer
2. Data Link Layer
3. Network Layer
4. Transport Layer
5. Session Layer
6. Presentation Layer
7. Application Layer

## 4. Associative Matching

Select the right transport layer protocol for the following application layer protocols:

- HTTP: TCP
- CoAP: UDP
- SMTP: TCP
- OpenVPN: both possible

## Group 3, hard

## 5. Short Answer

What is 2+2?

- 4

## 6. Forced Multiple Choice with Single Correct Answer

Is this valid ... code? <!-- @force_multi=true -->

```cpp
int *p = new int;
delete p;
```

- [x] C++
- [ ] C
- [ ] Java
````

For example, question 1 and 2 would have tags `Group 1` and `easy`.

Question 1 is named `1. Single Choice` and is going to be a single choice question automatically, as it only has one
correct answer (you can change that behaviour with inline configuration, see last question in example). The second
question is multiple choice.

### Inline Configuration

Some things can be configured with key-value pairs that look like `@{key}={value}` that you can put into paragraphs
(not code blocks etc.). They are also shown in the example above. To not make them visible, just wrap them in HTML
comments:

```markdown
Question Text <!-- @{key1}={value1} @{key2}={value2} -->
```

#### Implemented Configuration Options

| Option                             | Description                                                                          |
|------------------------------------|--------------------------------------------------------------------------------------|
| `@shuffle={true,false}`            | Shuffle answers randomly in Moodle (default: true, except enumerated matching)       |
| `@numbering={abc,ABC,123,iii,III}` | Sets numbering format<br>*Only for single / multiple choice questions!*              |
| `@force_multi=true`                | Forces single choice question (only one correct answer) to appear as multiple choice |

## Implementation Details

The tool uses [mistletoe](https://github.com/miyuchina/mistletoe) as a Markdown parser and to render Markdown to HTML.
[mistletoe](https://github.com/miyuchina/mistletoe) creates an [AST](https://en.wikipedia.org/wiki/Abstract_syntax_tree)
by instantiating a `Document` object:

```python
with open(file_path, 'r') as file:
	document = Document(file)
```

The AST is then traversed by the `parse(document: Document)` method of the `parser` file after initializing it with
configuration, which spits out object-oriented representations of the questions as a list of `Question` objects:

```python
parser = Parser(Parser.Config(...))
questions = parser.parse(document)
# questions = [Question, Question, Question, ...]
```

The `renderer` file does contain the said representational classes for `Question`s, `Answer`s and so on. It also
contains a `MoodleXmlRenderer` class which uses [lxml](https://lxml.de/) to convert the object representations into an
XML file which is importable in Moodle:

```python
renderer = MoodleXmlRenderer(MoodleXmlRenderer.Config(...))
xml = renderer.render(questions)
# xml = <XML string>
```

One bonus as the side effect of the modular approach is that it would be pretty easy to either make a new parser for
a non-Markdown language. The same goes for the renderer, which could be easily implemented for something non-XML.

Another bonus is that you can construct questions programmatically in a relatively straight-forward manner. See
`test.py` for an example.

### `Parser` class

The `Parser.parse(document: Document)` method just iterates over each of the children of the document. Then, it
differentiates between the different `mistletoe.BlockToken` subtypes and branches off into a method to handle parsing
the observed instance of the type.

When a `Paragraph` is found, this usually means that a new question starts. This (or the `parse_heading`method)
instantiates a `Question` object that is passed to the next iteration. In the next iteration, a `List` is expected
which takes the existing question object and adds answers to it. If a `Paragraph` or some other type in
`Parser.QUESTION_TEXT_TYPES` is found instead of a list, and a question was already constructed by a
paragraph before, its text will be rendered to HTML and added to the question. That's it, basically.

### `MoodleXmlRenderer` class

The implementation is probably trivial without explanation if you know the following stuff:

[lxml](https://lxml.de/) offers an implementation of the `ElementTree` API of Python. It is documented
[here](https://lxml.de/tutorial.html). The `MoodleXmlRenderer` class especially uses the so-called [*E-factory* of
lxml](https://lxml.de/tutorial.html#the-e-factory). With this, you can first create "building blocks" that can then
be called in cascades to build the structure of an XML file programmatically, nearly looking like the XML file itself.
Then, [lxml](https://lxml.de/) can just render it to XML.