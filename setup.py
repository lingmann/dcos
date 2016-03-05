from setuptools import setup


def get_advanced_templates():
    template_base = 'aws/templates/advanced/'
    template_names = ['advanced-master', 'advanced-priv-agent', 'advanced-pub-agent', 'infra', 'zen']

    return [template_base + name + '.json' for name in template_names]


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
    packages=['gen', 'gen.aws', 'gen.azure', 'providers', 'ssh'],
    install_requires=[
        'requests',
        'azure-common==1.0.0',
        'azure-storage==0.30.0',
        'boto3',
        'botocore',
        'coloredlogs',
        'pyyaml',
        'pytest',
        'retrying'],
    entry_points={
        'console_scripts': [
            'release=providers.release:main',
            'ccm-deploy-test=providers.test_installer_ccm:main',
        ],
    },
    package_data={
        'gen': [
            'cloud-config.yaml',
            'dcos-config.yaml',
            'dcos-metadata.yaml',
            'dcos-services.yaml',
            'aws/dcos-config.yaml',
            'aws/templates/aws.html',
            'aws/templates/cloudformation.json',
            'azure/cloud-config.yaml',
            'azure/azuredeploy-parameters.json',
            'azure/templates/acs.json',
            'azure/templates/azure.html',
            'azure/templates/azuredeploy.json',
            'coreos-aws/cloud-config.yaml',
            'coreos/cloud-config.yaml'
            ] + get_advanced_templates(),
        'providers': [
            '../docker/py.test/Dockerfile',
            '../docker/test_server/Dockerfile',
            '../docker/test_server/test_server.py',
            '../integration_test.py',
            '../scripts/ip-detect/aws.sh'],
    },
    zip_safe=False
)
