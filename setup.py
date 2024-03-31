from setuptools import setup

setup(
    name='ox',
    version='1.0',
    scripts=['ox_hw.py'],
    install_requires=[
        'argparse',
        'logging',
        'requests',
        'pydot',
        'graphviz'
    ]
)
