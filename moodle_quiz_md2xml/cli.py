import os
import argparse
import re
from glob import glob
from pathlib import Path
from configparser import ConfigParser
from typing import Dict, Union, List

# noinspection PyProtectedMember
from mistletoe import Document, ast_renderer
from pprint import pprint

from moodle_quiz_md2xml.parser import Parser
from moodle_quiz_md2xml.renderer import MoodleXmlRenderer


DESCRIPTION = 'Converts specially formatted Markdown files containing quiz questions to Moodle\'s quiz XML format'
EPILOG = '''It is allowed to add configuration options to the Markdown text that are interpreted by the parser. The options are:
@shuffle={true,false}\t\t\t- shuffle answers randomly in Moodle (default: true, except enumerated matching)
@numbering={abc,ABC,123,iii,IIII,none}\t- sets numbering format (only for single / multiple choice questions!)
@force_multi=true\t\t\t- forces single choice question (only one correct answer) to appear as multiple choice'''


def get_config() -> Dict[str, Union[str, List[str], Dict[str, str]]]:
	"""
	Reads configuration from ``default.ini`` or a file specified by program arguments, and merges them with program
	arguments (program arguments do overwrite values from configuration file).

	:return: configuration
	"""

	def get_arg_config():
		arg_parser = argparse.ArgumentParser(description=DESCRIPTION, epilog=EPILOG,
											 formatter_class=argparse.RawTextHelpFormatter,
											 argument_default=argparse.SUPPRESS)
		arg_parser.add_argument('input_files', metavar='INPUT_FILE', nargs='+',
								help='Markdown files to convert, wildcards '
									 'are allowed')
		arg_parser.add_argument('--config', '-c', dest='config_file', type=str, default=None, required=False,
								help='configuration file path (if not set: using packaged default.ini)')
		arg_parser.add_argument('--tags', '-t', dest='tags', type=str, required=False,
								help='comma-separated list of tags that shall always be added to questions')
		arg_parser.add_argument('--shuffle', '-s', dest='shuffle_answers', type=bool, required=False,
								help='shuffle answers by default (does not apply to enumeration matching questions), possible values: true (default), false')
		arg_parser.add_argument('--numbering', '-n', dest='numbering', type=str, required=False,
								choices=Parser.NUMBERING_OPTIONS,
								help='default numbering scheme for single / multiple choice questions')
		arg_parser.add_argument('--remove-comments', '-r', dest='remove_comments', type=bool, required=False,
								help='remove HTML comments from Markdown before doing any parsing, possible values: true (default), false')
		arg_parser.add_argument('--verbose', '-v', dest='verbose', action='store_true',
								help='enable some verbose / debug output')
		config = arg_parser.parse_args()

		if not hasattr(config, 'verbose'):
			config.verbose = False

		return vars(config)

	def get_file_config(file_path=None):
		config_parser = ConfigParser()
		file_path = os.path.join(Path(__file__).parent.absolute(), 'default.ini') if file_path is None else file_path
		with open(file_path) as file:
			config_parser.read_file(file)

		config = {}
		for key in ['numbering', 'shuffle_answers', 'remove_comments', 'general_tags', 'multichoice_tags', 'matching_tags',
					'shortanswer_tags', 'numerical_tags', 'matching_separator']:
			config[key] = config_parser.get('DEFAULT', key)

		# localization = {}
		# for key in ['correct_feedback', 'partially_correct_feedback', 'incorrect_feedback']:
		# 	localization[key] = config_parser.get('localization', key)
		# config['localization'] = localization

		return config

	arg_config = get_arg_config()
	file_config = get_file_config(arg_config['config_file'])

	# pprint(file_config)
	# pprint(arg_config)

	# merge both configs (conveniently they are dicts now)
	merged = {**file_config, **arg_config}  # merges both dicts, the second one is overwriting the first

	# reformat some stuff
	for key in ['general_tags', 'multichoice_tags', 'matching_tags', 'shortanswer_tags', 'numerical_tags']:
		merged[key] = merged[key].split(',')
	for key in ['remove_comments']:
		if type(merged[key]) is str:
			if merged[key] == 'yes':
				merged[key] = True
			else:
				merged[key] = False

	return merged


def main():
	config = get_config()
	if config['verbose'] is True:
		pprint(config)
	# pprint(vars(Parser.Config(**config)))

	parser = Parser(Parser.Config(**config))
	renderer = MoodleXmlRenderer(MoodleXmlRenderer.Config(**config))

	for raw_path in config['input_files']:
		# resolve wildcards
		file_paths = glob(raw_path)

		if len(file_paths) == 0:
			raise IOError('No Markdown file specified in path: ' + raw_path)

		for file_path in file_paths:
			print(file_path)

			with open(file_path, 'r') as file:
				raw_str = file.read()

				# remove HTML comments on request
				if config['remove_comments'] is True:
					raw_str = re.sub('(<!--.*?-->)', '', raw_str, flags=re.DOTALL)

				document = Document(raw_str)

			if document is None:
				raise IOError('Could not open specified Markdown file.')

			if config['verbose'] is True:
				pprint(ast_renderer.get_ast(document))

			questions = parser.parse(document)
			xml = renderer.render(questions)

			path = Path(file_path).with_suffix('.xml')
			with open(path, 'w') as file:
				file.write(xml.decode('UTF-8'))

	print('done')


if __name__ == '__main__':
	main()
