from levislib import version
from distutils.core import setup

setup(
	name=version.APP_NAME,
	version=version.APP_VERSION,
	description='Remote Monitoring and Management Agent',
	author='Simon A. F. Lund',
	author_email='safl@safl.dk',
	url='http://github.com/safl/levis',
	license='GNU GPL v3',
	scripts=['levis'],
	packages=['levislib']
)
