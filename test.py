from moodle_quiz_md2xml.renderer import Question, Answer, QuestionType, MoodleXmlRenderer

"""
Code that demonstrates how to use `moodle_quiz_md2xml.renderer` programmatically.
"""

if __name__ == '__main__':
	question = Question(
		'Language of Peru',
		'What is the official language of Peru?',
		QuestionType.MULTICHOICE,
		tags=['South America'],
		single_choice=True,
		answers=[
			Answer('Spanish', 1.0),
			Answer('German', 0.0),
			Answer('Portuguese', 0.0)
		]
	)

	renderer = MoodleXmlRenderer(MoodleXmlRenderer.Config())

	xml = renderer.render([question])
	print(xml.decode('utf-8'))
