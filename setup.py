from setuptools import setup, find_packages

setup(
    name="scraper_agent",
    version="0.1.0",
    description="A powerful web scraping framework with specialized data extractors",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="ScraperAgent Team",
    author_email="info@scraperagent.com",
    url="https://github.com/scraperagent/scraperagent",
    packages=find_packages(),
    install_requires=[
        "beautifulsoup4>=4.12.2",
        "requests>=2.31.0",
        "urllib3>=2.0.7",
        "playwright>=1.42.0",
        "lxml>=4.9.3",
        "python-dateutil>=2.8.2",
        "tqdm>=4.66.1",
        "jsonschema>=4.20.0",
        "validators>=0.22.0",
        "cssselect>=1.2.0",
        "user-agents>=2.2.0",
        "PyYAML>=6.0.1"
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.7.0",
            "isort>=5.12.0",
            "flake8>=6.1.0",
            "mypy>=1.5.1",
            "types-requests>=2.31.0",
            "types-beautifulsoup4>=4.12.0",
            "types-python-dateutil>=2.8.19",
        ]
    },
    entry_points={
        'console_scripts': [
            'scraper-agent=src.main:main',
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Text Processing :: Markup :: HTML"
    ],
) 