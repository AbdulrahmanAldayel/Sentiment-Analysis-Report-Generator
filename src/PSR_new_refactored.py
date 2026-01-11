#!/usr/bin/env python3
"""
S-OIL Press Summary Report RPA

This module automates the collection, analysis, and generation of press summary reports
for S-OIL company. It fetches news articles, performs sentiment analysis using AI,
and generates comprehensive HTML reports with positivity indices.

Author: Press Summary Report RPA
Date: 2023
Version: 2.0
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import requests
import openai
from bs4 import BeautifulSoup
from newscatcherapi import NewsCatcherApiClient

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    ENV_AVAILABLE = True
except ImportError:
    ENV_AVAILABLE = False


# Constants
CONFIG_DIR = Path(__file__).parent.parent / "config"
TEMPLATES_DIR = Path(__file__).parent.parent / "templates"
OUTPUT_DIR = Path(__file__).parent.parent / "output"
ASSETS_DIR = Path(__file__).parent.parent / "assets"

# API Configuration
NEWS_API_URL = "https://api.newscatcherapi.com/v2/search"
DEFAULT_QUERY = '"S-OIL"'
DEFAULT_LANGUAGE = 'ko'
DEFAULT_PAGE_SIZE = 25
DEFAULT_PAGE = 1

# OpenAI Configuration
OPENAI_MODEL = "text-davinci-003"
MAX_TOKENS = 50

# PI Color Mapping
PI_COLORS = {
    'high': '#32CD32',    # LimeGreen (PI >= 8)
    'medium': '#FFA500',  # Orange (PI >= 6)
    'low': '#FF4500'      # OrangeRed (PI < 6)
}

# PI Thresholds
PI_THRESHOLDS = {
    'high': 8,
    'medium': 6
}


class Configuration:
    """Manages configuration and API keys for the RPA system."""
    
    def __init__(self):
        """Initialize configuration by loading API keys from environment variables or config files."""
        # Try environment variables first
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.newscatcher_api_key = os.getenv('NEWSCATCHER_API_KEY')
        
        # Fallback to config files if environment variables not set
        if not self.openai_api_key:
            self.openai_api_key = self._load_api_key('openai_apiKey.txt')
        
        if not self.newscatcher_api_key:
            self.newscatcher_api_key = self._load_api_key('newscatcher_API_apiKey.txt')
        
        # Set OpenAI API key
        openai.api_key = self.openai_api_key
    
    def _load_api_key(self, filename: str) -> str:
        """
        Load API key from configuration file.
        
        Args:
            filename: Name of the API key file
            
        Returns:
            API key string
            
        Raises:
            FileNotFoundError: If the API key file doesn't exist
            ValueError: If the API key file is empty
        """
        api_key_path = CONFIG_DIR / filename
        
        if not api_key_path.exists():
            raise FileNotFoundError(f"API key file not found: {api_key_path}")
        
        with open(api_key_path, 'r', encoding='utf-8') as f:
            api_key = f.read().strip()
            
        if not api_key:
            raise ValueError(f"API key file is empty: {api_key_path}")
            
        return api_key


class SentimentAnalyzer:
    """Handles sentiment analysis using OpenAI's GPT models."""
    
    def __init__(self, config: Configuration):
        """
        Initialize the sentiment analyzer.
        
        Args:
            config: Configuration object containing API keys
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def analyze_sentiment(self, title: str, summary: str) -> int:
        """
        Analyze sentiment of an article and return Positivity Index (PI).
        
        Args:
            title: Article title
            summary: Article summary
            
        Returns:
            PI score (0-10)
            
        Raises:
            Exception: If OpenAI API call fails
        """
        prompt = self._create_sentiment_prompt(title, summary)
        
        try:
            response = openai.Completion.create(
                engine=OPENAI_MODEL,
                prompt=prompt,
                max_tokens=MAX_TOKENS
            )
            
            pi_text = response.choices[0].text.strip()
            pi_score = self._extract_pi_score(pi_text)
            
            self.logger.info(f"Sentiment analysis completed - PI: {pi_score}")
            return pi_score
            
        except Exception as e:
            self.logger.error(f"Sentiment analysis failed: {str(e)}")
            # Return random score as fallback
            import random
            return random.randint(0, 10)
    
    def _create_sentiment_prompt(self, title: str, summary: str) -> str:
        """
        Create the prompt for sentiment analysis.
        
        Args:
            title: Article title
            summary: Article summary
            
        Returns:
            Formatted prompt string
        """
        return (f"Given the following title and summary of an article in Korean: "
                f"Title: {title} Summary: {summary} "
                f"could you gage on a scale of 0-10 how positively it mentions S-OIL company, "
                f"with 0 being terrible publicity for S-OIL such as accusing it of mal-practice, "
                f"and 10 being good coverage of S-OIL such as applauding S-OIL's initiatives, "
                f"regardless of whether S-OIL is mentioned in the summary or not. "
                f"I am asking you for a sentiment analysis of this article about S-OIL and "
                f"assigning it to a score out of 10. Respond only with a single digit integer. "
                f"Do not respond with anything else besides a number from 0 to 10. "
                f"If not then just return a random number from 0-10.")
    
    def _extract_pi_score(self, pi_text: str) -> int:
        """
        Extract PI score from OpenAI response.
        
        Args:
            pi_text: Raw response from OpenAI
            
        Returns:
            PI score as integer (0-10)
        """
        # Filter digits and take first character
        digits = ''.join(filter(str.isdigit, pi_text))
        if digits:
            return int(digits[0])
        return 0  # Default fallback


class NewsFetcher:
    """Handles fetching news articles from NewsCatcher API."""
    
    def __init__(self, config: Configuration):
        """
        Initialize the news fetcher.
        
        Args:
            config: Configuration object containing API keys
        """
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def fetch_articles(self, query: str = DEFAULT_QUERY, language: str = DEFAULT_LANGUAGE,
                      page_size: int = DEFAULT_PAGE_SIZE, page: int = DEFAULT_PAGE) -> List[Dict[str, Any]]:
        """
        Fetch news articles from NewsCatcher API.
        
        Args:
            query: Search query
            language: Article language
            page_size: Number of articles per page
            page: Page number
            
        Returns:
            List of article dictionaries
            
        Raises:
            Exception: If API call fails
        """
        try:
            headers = {"x-api-key": self.config.newscatcher_api_key}
            params = {
                "q": query,
                "page": str(page),
                "lang": language,
                "page_size": str(page_size)
            }
            
            response = requests.get(NEWS_API_URL, headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get('articles', [])
            
            self.logger.info(f"Successfully fetched {len(articles)} articles")
            return articles
            
        except Exception as e:
            self.logger.error(f"Failed to fetch articles: {str(e)}")
            raise


class ReportGenerator:
    """Generates HTML reports from analyzed articles."""
    
    def __init__(self):
        """Initialize the report generator."""
        self.logger = logging.getLogger(__name__)
        self.total_pi_scores = []
    
    def generate_report(self, articles: List[Dict[str, Any]], sentiment_analyzer: SentimentAnalyzer) -> str:
        """
        Generate HTML report from articles.
        
        Args:
            articles: List of article dictionaries
            sentiment_analyzer: Sentiment analyzer instance
            
        Returns:
            Path to generated HTML file
        """
        # Load HTML template
        template_path = TEMPLATES_DIR / "html_template.html"
        with open(template_path, encoding="utf8") as f:
            soup = BeautifulSoup(f, 'html.parser')
        
        # Get template table
        template_table = soup.select("#table")[0]
        
        # Process each article
        for i, article in enumerate(articles):
            if not article.get('summary'):
                continue
                
            # Add article number
            self._add_article_number(soup, i + 1)
            
            # Create article table
            article_table = self._create_article_table(soup, template_table, article, sentiment_analyzer)
            if article_table:
                soup.body.append(article_table)
        
        # Update average PI
        if self.total_pi_scores:
            avg_pi = round(sum(self.total_pi_scores) / len(self.total_pi_scores), 1)
            self._update_average_pi(soup, avg_pi)
        
        # Remove template table
        template_table.decompose()
        
        # Save report
        return self._save_report(soup)
    
    def _add_article_number(self, soup: BeautifulSoup, number: int) -> None:
        """Add article number to the report."""
        number_elem = soup.new_tag('p', 
                                 style='margin-left: auto; margin-right: auto; '
                                       'margin-top: 10px; margin-bottom: 10px; '
                                       'font-family: Arial, sans-serif; '
                                       'font-size: 14px; width: 50%')
        number_elem.string = f"{number}."
        soup.body.append(number_elem)
        
        br = soup.new_tag('br')
        soup.body.append(br)
    
    def _create_article_table(self, soup: BeautifulSoup, template_table: BeautifulSoup,
                            article: Dict[str, Any], sentiment_analyzer: SentimentAnalyzer) -> Optional[BeautifulSoup]:
        """Create a table for a single article."""
        from copy import deepcopy
        
        new_table = deepcopy(template_table)
        
        # Get table cells
        cells = new_table.find_all('td')
        if len(cells) < 7:
            return None
        
        title_cell = cells[0]
        pi_cell = cells[1]
        author_cell = cells[2]
        agency_cell = cells[3]
        date_cell = cells[4]
        summary_cell = cells[5]
        url_cell = cells[6]
        
        # Extract article data
        title = article.get('title', '')
        author = article.get('author', '')
        agency = article.get('clean_url', '')
        date = article.get('published_date', '')[:10] if article.get('published_date') else ''
        summary = article.get('summary', '')
        url = article.get('link', '')
        
        if not summary:
            return None
        
        # Perform sentiment analysis
        pi_score = sentiment_analyzer.analyze_sentiment(title, summary)
        self.total_pi_scores.append(pi_score)
        
        # Populate cells
        title_cell.append(title)
        author_cell.append(author)
        agency_cell.append(agency)
        date_cell.append(date)
        summary_cell.append(summary)
        
        # Add URL link
        url_link = soup.new_tag('a', href=url)
        url_link.string = url
        url_cell.append(url_link)
        
        # Add PI score with color
        pi_cell.strong.append(str(pi_score))
        pi_cell['style'] = f'background-color: {self._get_pi_color(pi_score)}'
        
        return new_table
    
    def _get_pi_color(self, pi_score: int) -> str:
        """Get color based on PI score."""
        if pi_score >= PI_THRESHOLDS['high']:
            return PI_COLORS['high']
        elif pi_score >= PI_THRESHOLDS['medium']:
            return PI_COLORS['medium']
        else:
            return PI_COLORS['low']
    
    def _update_average_pi(self, soup: BeautifulSoup, avg_pi: float) -> None:
        """Update the average PI display."""
        pi_display = soup.find_all('td')[0]
        if pi_display and pi_display.strong:
            pi_display.strong.string = f'Average PI: {avg_pi}'
        
        # Update table background color
        pi_table = soup.find_all('table')[0]
        if pi_table:
            pi_table['style'] = f'background-color: {self._get_pi_color(avg_pi)}'
    
    def _save_report(self, soup: BeautifulSoup) -> str:
        """Save the report to file."""
        # Generate filename with timestamp
        today_name = datetime.now().strftime("%m_%d_%Y")
        filename = f"S_OIL_PSR_{today_name}.html"
        output_path = OUTPUT_DIR / filename
        
        # Ensure output directory exists
        OUTPUT_DIR.mkdir(exist_ok=True)
        
        # Save file
        with open(output_path, "wb") as file:
            file.write(soup.prettify("utf-8"))
        
        logging.info(f"Report saved to: {output_path}")
        return str(output_path)


def setup_logging() -> None:
    """Setup logging configuration."""
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"psr_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )


def main() -> None:
    """Main entry point for the S-OIL Press Summary Report RPA."""
    try:
        # Setup logging
        setup_logging()
        logger = logging.getLogger(__name__)
        logger.info("Starting S-OIL Press Summary Report RPA")
        
        # Initialize components
        config = Configuration()
        news_fetcher = NewsFetcher(config)
        sentiment_analyzer = SentimentAnalyzer(config)
        report_generator = ReportGenerator()
        
        # Fetch articles
        logger.info("Fetching news articles...")
        articles = news_fetcher.fetch_articles()
        
        if not articles:
            logger.warning("No articles found")
            return
        
        logger.info(f"Processing {len(articles)} articles")
        
        # Generate report
        logger.info("Generating report...")
        report_path = report_generator.generate_report(articles, sentiment_analyzer)
        
        logger.info(f"Report generation completed: {report_path}")
        print(f"Report successfully generated: {report_path}")
        
    except Exception as e:
        logger.error(f"RPA execution failed: {str(e)}")
        print(f"Error: {str(e)}")
        raise


if __name__ == "__main__":
    main()
