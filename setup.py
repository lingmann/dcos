from setuptools import setup, find_packages

setup(
    name='dcos_image',
    version='0.1',
    description='DCOS Image creation, management, install utilities',
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
    # TODO(cmaloney): remove find_packages()
    packages=['gen', 'providers', 'ssh', 'deploy'] + find_packages(),
    install_requires=[
        'requests==2.8.1',
        'azure-storage==0.20.2',
        'boto3',
        'botocore',
        'coloredlogs',
        'jinja2',
        'pyyaml',
        'pytest',
        'retrying',
        'termcolor'],
    entry_points={
        'console_scripts': [
            'release=providers.release:main',
            'genconf=providers.genconf:main',
            'ccm-deploy-test=providers.test_genconf_ccm:main',
        ],
    },
    package_data={
        '': [
            '*.yaml',
            '*/*.yaml',
            'install_requirements'],
        'gen': [
            '*/*.yaml',
            'aws/templates/aws.html',
            'aws/templates/cloudformation.json',
            'azure/azuredeploy-parameters.json',
            'azure/templates/azure.html',
            'azure/templates/azuredeploy.json',
            'vagrant/config.rb',
            'vagrant/make_dcos_vagrant.sh.in',
            'vagrant/Vagrantfile'],
        'providers': [
            '../docker/py.test/Dockerfile',
            '../docker/test_server/Dockerfile',
            '../docker/test_server/test_server.py',
            '../integration_test.py'],
    },
    zip_safe=False
)
