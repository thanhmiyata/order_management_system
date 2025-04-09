from setuptools import setup, find_packages

def read_requirements():
    with open('requirements.txt') as req:
        content = req.read()
        requirements = content.split('\n')
    # Filter out comments and empty lines
    return [req for req in requirements if req and not req.startswith('#')]

setup(
    name='temporal_order_system',
    version='0.1.0',
    packages=find_packages(exclude=["tests*"]), # Automatically find packages
    include_package_data=True,
    install_requires=read_requirements(),
    author='Your Name', # Replace with your name
    author_email='your.email@example.com', # Replace with your email
    description='Order Management System using Temporal and FastAPI',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/your-repo-name', # Replace with your repo URL
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License", # Choose your license
        "Operating System :: OS Independent",
        "Framework :: FastAPI",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
    ],
    python_requires='>=3.9',
)
