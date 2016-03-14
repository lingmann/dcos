from setuptools import setup

setup(
    name='pkgpanda',
    version='0.8',
    description='DCOS package manager and utilities',
    url='https://mesosphere.com',
    author='Mesosphere, Inc.',
    author_email='support@mesosphere.io',
    license='TODO',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: TODO License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
    ],
    packages=['pkgpanda', 'pkgpanda.build'],
    install_requires=['docopt', 'requests'],
    entry_points={
        'console_scripts': [
            'pkgpanda=pkgpanda.cli:main',
            'mkpanda=pkgpanda.build.cli:main',
        ],
    },
    zip_safe=True
)
