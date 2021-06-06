import re
from typing import Union, List as PythonList

# noinspection PyProtectedMember
from mistletoe.block_token import Document, Heading, Paragraph, List, ListItem, CodeFence
from mistletoe.html_renderer import HTMLRenderer
# noinspection PyProtectedMember
from mistletoe.span_token import RawText, SpanToken, add_token as add_span_token

from moodle_quiz_md2xml.renderer import Question, SubQuestion, QuestionType, Answer


class Parser:
	"""
	Parser thar parses :py:class:`mistletoe.block_token.Document` to list of :py:class:`renderer.Question` objects.

	See :py:meth:`~Parser.parse` method for info about usage.
	"""
	NUMBERING_OPTIONS = ['abc', 'ABC', '123', 'iii', 'IIII']
	NUMBERING_KEYS = ['numbering', 'answernumbering']
	SHUFFLE_ANSWERS_KEYS = ['suffleanswers', 'shuffle_answers', 'shuffle']
	FORCE_MULTIPLE_CHOICE_KEYS = ['force_multi', 'force_multiple_choice', 'multi']
	TRUE_REPRESENTATIONS = ['true', 'yes', '1']
	FALSE_REPRESENTATIONS = ['false', 'no', '0']
	QUESTION_TEXT_TYPES = [CodeFence]  # can follow paragraph and will just be added to question text rendered as HTML

	html_tag_pattern = re.compile(r'(<!--.*?-->|<[^>]*>)')  # matches all HTML tags

	class Config:
		"""
		Configuration for initializing :py:class:`~Parser` object
		"""

		# noinspection PyUnusedLocal
		def __init__(self, numbering: str = 'abc', shuffle_answers: bool = True, general_tags: PythonList[str] = None,
					 multichoice_tags: PythonList[str] = None, matching_tags: PythonList[str] = None,
					 shortanswer_tags: PythonList[str] = None, numerical_tags: PythonList[str] = None,
					 matching_separator: str = ':', **unused):
			"""
			Initializes configuration.

			:param numbering: numbering of answers, possible values: abc, ABC, 123, iii (for i., ii., iii.),
				IIII (for I., II., III.)
			:param shuffle_answers: shuffle answers by default (does not apply to enumeration matching questions)
			:param general_tags: list of tags that shall always be added to every question
			:param multichoice_tags: list of tags that shall be added to multiple choice questions
			:param matching_tags: list of tags that shall be added to matching questions
			:param shortanswer_tags: list of tags that shall be added to short answer questions
			:param numerical_tags: list of tags that shall be added to numerical questions
			:param matching_separator: character to separate key and value in associative (non-enumerated) matching
				questions
			:param kwargs: unused
			"""
			self.numbering = numbering
			self.shuffle_answers = shuffle_answers
			self.general_tags = general_tags if general_tags is not None else []
			self.multichoice_tags = multichoice_tags if multichoice_tags is not None else []
			self.matching_tags = matching_tags if matching_tags is not None else []
			self.shortanswer_tags = shortanswer_tags if shortanswer_tags is not None else []
			self.numerical_tags = numerical_tags if numerical_tags is not None else []
			self.matching_separator = matching_separator

	# our own span token for inline config strings with syntax @key=val
	class _InlineConfig(SpanToken):
		pattern = re.compile(r"@([^=]+)=([^\s=]+)")  # @key=val
		parse_inner = False

		def __init__(self, match):
			self.key = match.group(1)
			self.value = match.group(2)

	# encapsulate existing HTML renderer to add own span tokens and change some characteristics
	class _HTMLRenderer(HTMLRenderer):
		def __init__(self):
			# add our span token to be rendered
			super().__init__(Parser._InlineConfig)

		# noinspection PyMethodMayBeStatic
		def render_inline_config(self, token):
			template = '@{key}={value}'
			return template.format(key=token.key, value=token.value)

		# overwrite method to disable escaping HTML symbols (makes problems for using HTML in Moodle XML)
		@staticmethod
		def escape_html(raw):
			return raw

	def __init__(self, config: Config):
		"""
		Initializes parser with given configuration.

		:param config: object containing configuration values
		"""
		self.config = config
		self._question_num = 1

		# add custom token to the loop
		# noinspection PyTypeChecker
		add_span_token(self._InlineConfig)

	def new_question(self, name: str = None, text: str = None) -> Question:
		question = Question(name, text)

		question.shuffle_answers = self.config.shuffle_answers
		question.numbering = self.config.numbering

		self._question_num += 1
		return question

	def parse_heading(self, heading: Heading) -> Union[Question, PythonList[str], None]:
		if heading.level == 1:
			# headings are separated into tags used for questions in Moodle

			if len(heading.children) != 1 or type(heading.children[0]) is not RawText:
				print('[Warning] Not using a heading for tags because it is not just simple text/symbols.')
				return

			return list(map(str.strip, heading.children[0].content.split(',')))
		elif heading.level == 2:
			# specifies the Question name explicitly

			if len(heading.children) != 1 or type(heading.children[0]) is not RawText:
				print('[Warning] Not using a heading as question name because it is not just simple text/symbols.')
				return

			name = heading.children[0].content.strip()
			return self.new_question(name)
		else:
			print('[Warning] Heading of level {} will be ignored.'.format(heading.level))

	def parse_paragraph(self, paragraph: Paragraph, question: Question = None) -> Question:
		# paragraph is the question or task description

		def apply_inline_config(config: Parser._InlineConfig, question: Question):
			key = config.key.lower()
			value = config.value

			if key in self.SHUFFLE_ANSWERS_KEYS:
				value = value.lower()

				if value in self.TRUE_REPRESENTATIONS:
					question.shuffle_answers = True
				elif value in self.FALSE_REPRESENTATIONS:
					question.shuffle_answers = False
				else:
					raise SyntaxError('Inline configuration \'{}\' has invalid boolean value \'{}\'. Use \'true\' or '
									  '\'false\' instead.'.format(key, value))
			elif key in self.NUMBERING_KEYS:
				if value not in self.NUMBERING_OPTIONS:
					raise SyntaxError(
						'Inline configuration \'{}\' has invalid value \'{}\'. Use [{}] instead.'.format(key, value,
																										 ', '.join(
																											 self.NUMBERING_OPTIONS)))

				question.numbering = value
			elif key in self.FORCE_MULTIPLE_CHOICE_KEYS:
				question.single_choice = 'false'  # 'false' string is the marker for forced multiple choice
			else:
				raise SyntaxError('Inline configuration \'{}\' is unknown to the parser.'.format(key))

		def construct_name(text: str):
			text = self.html_tag_pattern.sub('', text)
			text = text[:64] if len(text) > 64 else text
			return '{}. {}'.format(self._question_num, text)

		# render HTML for question text
		with self._HTMLRenderer() as renderer:  # TODO: this might not be the best idea, maybe reuse renderers
			text = renderer.render(paragraph)

		# make Question object, setting default values so they can already be overwritten by inline config
		# (some kwargs might not be actually needed by the question type)
		if question is None:
			# no name was set beforehand with heading level 2, so we need to construct one
			name = construct_name(text)
			question = self.new_question(name, text)
		else:
			# name was already set

			if question.text is None:
				question.text = ''

			question.text += text

		# look for _InlineConfig objects in children which might re-configure some aspects of the question
		for child in paragraph.children:
			if type(child) is self._InlineConfig:
				apply_inline_config(child, question)

		return question

	@classmethod
	def render_list_item(cls, item: ListItem) -> str:
		html = ''

		# don't parse paragraph as <p>{text}</p> but rather as {text} only
		# (that's because we may split HTML later on, also we don't need the <p></p>)
		if type(item.children[0]) is Paragraph:
			children = item.children[0].children
		else:
			children = item.children

		for child in children:
			with cls._HTMLRenderer() as renderer:  # TODO: this might not be the best idea, maybe reuse renderers
				html += renderer.render(child)

		return html

	def parse_list_as_multichoice(self, list_: List, question: Question):
		answers = []
		num_correct_answers = 0
		num_wrong_answers = 0

		# first create some answers which we can work on, and collect some statistics
		for item in list_.children:
			if len(item.children) < 1:
				raise SyntaxError('A list item has no text.')
			if len(item.children) > 1:
				raise SyntaxError('A list item has multiple paragraphs, while only one is allowed in implementation.')

			# the first child of a list item should always be a paragraph
			assert (type(item.children[0]) is Paragraph)

			# check if the paragraph has children (= list item has any text)
			if len(item.children[0].children) < 1:
				raise SyntaxError('A list item has no text.')

			# ensure that we don't throw errors when accessing string behind RawText
			text_with_checkbox = item.children[0].children[0]
			if type(text_with_checkbox) is not RawText:
				raise SyntaxError(
					'On single or multiple choice questions, list items are expected to start with `[ ]` or `[x]`.')

			# first children of paragraph should be RawText in order to have `[ ] ` or `[x] ` at beginning
			if text_with_checkbox.content.startswith('[ ] '):
				fraction = False
				num_wrong_answers += 1
			elif text_with_checkbox.content.startswith('[x] '):
				fraction = True
				num_correct_answers += 1
			else:
				raise SyntaxError(
					'On single or multiple choice questions, list items are expected to start with `[ ]` or `[x]`.')

			# remove `[ ] ` or `[x] ` at beginning (4 characters)
			text_with_checkbox.content = text_with_checkbox.content[4:]

			# The only children a list item has is usually a RawText, but sometimes it consists of multiple elements,
			# e.g. RawText, InlineCode, RawText. We use self.render_list_item to just render the children to a single
			# string containing HTML, which is used in Moodle XML anyway.
			text_rendered_html = self.render_list_item(item)

			answer = Answer(text_rendered_html, fraction)
			answers.append(answer)

		# calculate the fraction that shall be set for correct answers
		if num_correct_answers > 0:
			fraction_for_correct_answers = 1 / num_correct_answers

			if num_wrong_answers > 0:
				if num_correct_answers == 1:
					# single choice (but not if question.single_choice is a string, that is the marker for forced
					# multiple choice)
					if type(question.single_choice) is not str:
						question.single_choice = True
					fraction_for_wrong_answers = 0.0
				else:
					fraction_for_wrong_answers = 1 / num_wrong_answers
			else:
				fraction_for_wrong_answers = None
		else:
			raise SyntaxError('Single/multiple choice questions need at least one correct answer.')

		# iterate over answers to complete their representation
		for answer in answers:
			if answer.fraction is True:
				answer.fraction = fraction_for_correct_answers
			else:
				answer.fraction = -fraction_for_wrong_answers

		question.type = QuestionType.MULTICHOICE
		question.tags += self.config.multichoice_tags
		question.answers = answers

	def parse_list_as_enumerated_matching(self, list_: List, question: Question):
		subquestions = []

		for item in list_.children:
			text = self.render_list_item(item)
			answer = Answer(text)

			# item.leader is e.g. '1.', '2.', ...
			subquestion = SubQuestion(item.leader, answer)
			subquestions.append(subquestion)

		question.type = QuestionType.MATCHING
		question.subquestions = subquestions
		question.tags += self.config.matching_tags

		# for enumerated subquestions it does not make sense to shuffle, but for not enumerated ones it may in the future
		question.shuffle_answers = False

	def parse_list_as_associative_matching(self, list_: List, question: Question):
		subquestions = []

		for item in list_.children:
			if len(item.children) < 1:
				raise SyntaxError('A list item has no text.')
			if len(item.children) > 1:
				raise SyntaxError('A list item has multiple paragraphs, while only one is allowed in implementation.')

			# the first child of a list item should always be a paragraph
			assert (type(item.children[0]) is Paragraph)

			# check if the paragraph has children (= list item has any text)
			if len(item.children[0].children) < 1:
				raise SyntaxError('A list item has no text.')

			# render to HTML to process further
			text_rendered_html = self.render_list_item(item)

			if self.config.matching_separator not in text_rendered_html:
				raise SyntaxError(
					'A list item of a question that was assumed to be an associative matching question does not '
					'contain the separator \'{}\''.format(
						self.config.matching_separator))

			parts = text_rendered_html.split(self.config.matching_separator, 1)
			if len(parts) < 2:
				raise SyntaxError(
					'A list item of a question that was assumed to be an associative matching question does not '
					'contain a key/question and a value/answer.')

			answer = Answer(parts[1].lstrip())
			subquestion = SubQuestion(parts[0], answer)
			subquestions.append(subquestion)

		question.type = QuestionType.MATCHING
		question.tags += self.config.matching_tags
		question.subquestions = subquestions

	def parse_list_as_short_answer_or_numerical(self, list_: List, question: Question):
		text_rendered_html = self.render_list_item(list_.children[0])
		answer = Answer(text_rendered_html, fraction=1.0)

		if text_rendered_html.isnumeric():
			question.type = QuestionType.NUMERICAL
			question.tags += self.config.numerical_tags
		else:
			question.type = QuestionType.SHORTANSWER
			question.tags += self.config.shortanswer_tags

		question.answers = [answer]

	def parse_unordered_list(self, list_: List, question: Question):
		if len(list_.children) < 1:
			raise SyntaxError('A list is empty.')

		item = list_.children[0]
		if len(item.children) < 1:
			raise SyntaxError('A list item has no text.')

		if len(list_.children) == 1:
			self.parse_list_as_short_answer_or_numerical(list_, question)
			return

		assert (type(item.children[0]) is Paragraph)

		paragraph = item.children[0]
		if len(paragraph.children) < 1:
			raise SyntaxError('A list item has no text.')

		if type(paragraph.children[0]) is RawText and (
				paragraph.children[0].content.lower().startswith('[x] ') or paragraph.children[0].content.startswith(
			'[ ] ')):
			self.parse_list_as_multichoice(list_, question)
		else:
			self.parse_list_as_associative_matching(list_, question)

	def parse_list(self, list_: List, question: Question):
		# if list is unordered
		if list_.start is None:
			# this means that this list either represents a single or multiple choice question,
			# or it is a not-enumerated matching question, or it is a rare short answer question
			self.parse_unordered_list(list_, question)
		# else list is ordered
		else:
			# this means that this list represents the options for a matching question that contains subquestions with
			# numbers as text (enumerated matching)
			self.parse_list_as_enumerated_matching(list_, question)

	def parse(self, document: Document) -> PythonList[Question]:
		"""
		Parses a :py:class:`~mistletoe.block_token.Document` that was parsed by	:py:mod:`mistletoe`	and its text
		originally written in the special Markdown syntax for Moodle quizzes explained in the README.

		:param document: mistletoe document to parse
		:return: list of Moodle questions in object representation
		"""
		questions = []
		tags = []
		last_payload = None

		for child in document.children:
			type_ = type(child)

			if type_ is Heading:
				# yields a question object or tags list to apply later on
				payload = self.parse_heading(child)

				if type(payload) is Question:
					last_payload = payload
				elif type(payload) is list:
					tags = payload
			elif type_ is Paragraph:
				# to ensure that last_payload is either a question or none
				if last_payload is not None and type(last_payload) is not Question:
					raise SyntaxError('A {} should not be followed by a paragraph.'.format(type(last_payload).__name__))

				# always yields a question (not necessarily a new one)
				question = self.parse_paragraph(child, last_payload)
				question.tags = tags.copy() + self.config.general_tags

				last_payload = question
			elif type_ is List:
				# every list should follow a paragraph, whose parser created a new Question already
				if last_payload is None or type(last_payload) is not Question:
					raise SyntaxError('A list was found but there was no paragraph before.')

				self.parse_list(child, last_payload)

				# now, the Question should be complete and we add it to the list
				questions.append(last_payload)

				last_payload = None
			# for the types that just should be added to text as rendered HTML to the last observed question
			elif type_ in self.QUESTION_TEXT_TYPES:
				if last_payload is None or type(last_payload) is not Question:
					raise SyntaxError('A {} needs to follow a question (paragraph).'.format(type_.__name__))

				assert (last_payload.text is not None)

				with self._HTMLRenderer() as renderer:  # TODO: this might not be the best idea, maybe reuse renderers
					last_payload.text += renderer.render(child)
			else:
				# ignore other types for now, but tell user
				print('[Warning] Element of type {} was ignored since its type is unknown to this program.'.format(
					child.__class__.__name__))

		return questions
