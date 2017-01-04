#!/usr/bin/env python

from setuptools import *
setup(
	packages = find_packages(exclude=['test', 'test.*']),
	description='symlink management',
	entry_points={'console_scripts': ['daglink=daglink:main']},
	install_requires=['pyyaml', 'whichcraft'],
	long_description='',
	name='daglink',
	py_modules=['daglink'],
	url='https://github.com/timbertson/daglink',
	version='0.6',
)
