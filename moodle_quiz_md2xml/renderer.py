from enum import Enum
from typing import List
from lxml import etree
from lxml.builder import ElementMaker


class Answer:
	"""
	Answer to a question represented by :py:class:`~Question` or :py:class:`~SubQuestion`.

	Those are basically converted to the answers you can tick/choose in Moodle.
	"""

	def __init__(self, text: str, fraction: float = None):
		"""
		Initializes answer.

		:param text: description
		:param fraction: float from 0.0 to 1.0 specifying how much this answer contributes to
		grade (all answers need to sum up to 1.0)
		"""
		self.text = text
		self.fraction = fraction


class QuestionType(Enum):
	"""
	Question types that :py:class:`~Question` objects can represent.
	"""
	MULTICHOICE = 'multichoice'
	MATCHING = 'matching'
	SHORTANSWER = 'shortanswer'
	UNKNOWN = None


class SubQuestion:
	"""
	Subquestion associated with a question of type :py:const:`~QuestionType.MATCHING`.

	Those are basically converted to the fields you need to select the matching answer for in Moodle.
	"""

	def __init__(self, text: str, answer: Answer):
		"""
		Initializes subquestion.

		:param text: description
		:param answer: correct answer
		"""
		self.text = text
		self.answer = answer


class Question:
	"""
	Question representing a question that can be added to a Moodle quiz.
	"""

	def __init__(self, name: str = None, text: str = None, type_: QuestionType = QuestionType.UNKNOWN,
				 tags: List[str] = None,
				 shuffle_answers: bool = True, numbering: str = 'abc', answers: List[Answer] = None,
				 single_choice: bool = False, subquestions: List[SubQuestion] = None):
		"""
		Initializes question.

		:param name: name (more like a short human-readable identifier)
		:param text: description (the question you ask)
		:param type_: question type
		:param tags: tags
		:param shuffle_answers: shuffle answers
		:param numbering: numbering of answers, possible values: abc, ABC, 123, iii (for i., ii., iii.),
			IIII (for I., II., III.), none
		:param answers: list of possible answers (only for :py:const:`~QuestionType.MULTICHOICE` and
			:py:const:`~QuestionType.SHORTANSWER`)
		:param single_choice: single choice (only for :py:const:`~QuestionType.MULTICHOICE`)
		:param subquestions: list of subquestions (only for :py:const:`~QuestionType.MATCHING`)
		"""
		self.name = name
		self.text = text
		self.type = type_  # usually not known in advance
		self.tags = tags if tags is not None else []
		self.shuffle_answers = shuffle_answers  # works for answers and subquestions
		self.numbering = numbering

		# when self.type is QuestionType.MULTICHOICE
		self.single_choice = single_choice  # single choice?

		# when self.type is QuestionType.MATCHING
		self.subquestions = subquestions if subquestions is not None else []

		# when self.type is QuestionType.MULTICHOICE or self.type is QuestionType.SHORTANSWER
		self.answers = answers if answers is not None else []  # will contain only one element for QuestionType.MATCHING


class Renderer:
	"""
	Abstract renderer that renders object representations of Moodle questions (list of :py:class:`renderer.Question`
	objects) to another format.
	"""

	@staticmethod
	def render(questions: List[Question]):
		"""
		Abstract method to render list of :py:class:`~Question` objects to another format.

		:param questions: list of questions
		"""
		pass


class MoodleXmlRenderer(Renderer):
	"""
	Renderer that renders object representations of Moodle questions (list of :py:class:`renderer.Question`
	objects) to an XML string that Moodle can import to a pool of quiz questions.
	"""

	class Config:
		"""
		Configuration for initializing :py:class:`~MoodleXmlRenderer` object
		"""

		def __init__(self, localization: dict = None, **unused):
			"""
			Initializes configuration.

			:param localization: dictionary that contains localized string values
			:param unused: unused, just there to allow more keyword arguments to be passed than needed
			"""
			self.localization = localization if localization is not None else {}

	class _LxmlElementFactory:
		# https://lxml.de/apidoc/lxml.builder.html
		E = ElementMaker()
		QUIZ = E.quiz
		QUESTION = E.question
		NAME = E.name
		TEXT = E.text
		QUESTIONTEXT = E.questiontext
		DEFAULTGRADE = E.defaultgrade  # default number of total points when the question is added to a quiz
		PENALTY = E.penalty  # penalty for each incorrect try when multiple tries are allowed in a quiz
		HIDDEN = E.hidden
		SINGLE = E.single
		SHUFFLEANSWERS = E.shuffleanswers
		ANSWERNUMBERING = E.answernumbering
		CORRECTFEEDBACK = E.correctfeedback
		PARTIALLYCORRECTFEEDBACK = E.partiallycorrectfeedback
		INCORRECTFEEDBACK = E.incorrectfeedback
		SHOWNUMCORRECT = E.shownumcorrect
		SUBQUESTION = E.subquestion
		ANSWER = E.answer
		TAGS = E.tags
		TAG = E.tag

	def __init__(self, config: Config):
		"""
		Initializes parser with given configuration.

		:param config: object containing configuration values
		"""
		self.config = config

	def render(self, questions: List[Question]) -> str:
		"""
		Renders list of list of :py:class:`~Question` objects to an XML document that Moodle is able to import to a
		pool of quiz questions.

		:rtype: XML string compatible with Moodle XML quiz format
		"""
		e = self._LxmlElementFactory
		xml_root = e.QUIZ()

		for question in questions:
			xml_question = e.QUESTION(
				e.NAME(e.TEXT(question.name)),
				e.QUESTIONTEXT(e.TEXT(question.text), format='html'),
				# e.GENERALFEEDBACK(...),
				e.DEFAULTGRADE('1.0000000'),  # default number of total points when the question is added to a quiz
				e.PENALTY('0.3333333'),  # penalty for each incorrect try when multiple tries are allowed in a quiz
				e.HIDDEN('0'),
				# e.IDNUMBER(...),
				e.TAGS(*[e.TAG(e.TEXT(tag)) for tag in question.tags]),
				type=question.type.value
			)

			if question.type == QuestionType.MULTICHOICE or question.type == QuestionType.MATCHING:
				xml_question.append(e.SHUFFLEANSWERS(str(question.shuffle_answers).lower()))
				# xml_question.append(e.SHOWNUMCORRECT())

				# xml_question.append(
				# 	e.CORRECTFEEDBACK(e.TEXT(self.config.localization['correct_feedback'], format='html')))
				# xml_question.append(
				# 	e.PARTIALLYCORRECTFEEDBACK(
				# 		e.TEXT(self.config.localization['partially_correct_feedback'], format='html')))
				# xml_question.append(e.INCORRECTFEEDBACK(
				# 	e.TEXT(self.config.localization['incorrect_feedback'], format='html')))

			if question.type == QuestionType.MULTICHOICE:
				xml_question.append(e.SINGLE(str(question.single_choice).lower()))
				xml_question.append(e.ANSWERNUMBERING(question.numbering))

			if question.type == QuestionType.MULTICHOICE or question.type == QuestionType.SHORTANSWER:
				for answer in question.answers:
					xml_question.append(
						e.ANSWER(
							e.TEXT(answer.text),
							# e.FEEDBACK(...),
							fraction=str(answer.fraction * 100.0),
							format='html'
						)
					)
			elif question.type == QuestionType.MATCHING:
				for subquestion in question.subquestions:
					xml_question.append(
						e.SUBQUESTION(
							e.TEXT(subquestion.text),
							e.ANSWER(e.TEXT(subquestion.answer.text)),
							format='html'
						)
					)

			xml_root.append(xml_question)

		return etree.tostring(xml_root, encoding='UTF-8', pretty_print=True)
