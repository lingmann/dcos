from setuptools import setup, find_packages

setup(
    name='dcos_image',
    version='0.1',
    description='DCOS Image creation, management, isntall utilities',
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
    packages=['gen', 'providers', 'ssh', 'deploy'] + find_packages(),
    install_requires=[
        'azure-storage==0.20.2',
        'boto3',
        'botocore',
        'jinja2',
        'requests',
        'pyyaml',
        'pytest'],
    entry_points={
        'console_scripts': [
            'release=providers.release:main',
            'genconf=providers.genconf:main',
        ],
    },
    package_data={
        '': ['*.yaml', '*/*.yaml', 'install_requirements'],
        'gen': [
            '*/*.yaml',
            'aws/templates/aws.html',
            'aws/templates/cloudformation.json',
            'azure/azuredeploy.json',
            'azure/azuredeploy-parameters.json',
            'azure/templates/azure.html',
            'vagrant/config.rb',
            'vagrant/make_dcos_vagrant.sh.in',
            'vagrant/Vagrantfile',
            'deploy/preflight.sh']
    },
    zip_safe=False
)
