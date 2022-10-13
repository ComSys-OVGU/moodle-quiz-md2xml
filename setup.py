from setuptools import setup

setup(name='moodle_quiz_md2xml',
	  version='1.0',
	  description='Tool and module to convert strictly formatted Markdown files to Moodle\'s XML format which can be '
				  'imported easily',
	  url='https://github.com/ComSys-OVGU/moodle-quiz-md2xml',
	  author='Jon-Mailes Graeffe',
	  author_email='jgraeffe@ovgu.de',
	  license='MIT',
	  packages=['moodle_quiz_md2xml'],
	  install_requires=['mistletoe>=0.9.0', 'lxml>=4.9.1'],
	  python_requires='~=3.5',
	  include_package_data=True,
	  entry_points={
		  'console_scripts': ['moodle-md2xml=moodle_quiz_md2xml.cli:main']
	  },
	  zip_safe=False)
