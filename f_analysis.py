"""
Fundamental & Sentiment Analysis Module for MT5 ICT Fibonacci Trading Bot
Analyzes financial news, social media sentiment, and fundamental factors (COT reports, economic indicators)
Provides trend confirmation from macro perspective

Usage:
    from f_analysis import NewsSentimentAnalyzer, FundamentalAnalyzer
    
    news_analyzer = NewsSentimentAnalyzer()
    sentiment_score = news_analyzer.analyze_sentiment('EURUSD')
    
    fund_analyzer = FundamentalAnalyzer()
    fund_score = fund_analyzer.get_fundamental_score('EURUSD')
"""

import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Tuple, List
from config import CONFIG

logger = logging.getLogger(__name__)

# ==================== NEWS & SOCIAL MEDIA SENTIMENT ANALYSIS ====================

class NewsSentimentAnalyzer:
    """
    Analyzes sentiment from financial news and social media
    Data sources:
    - Financial news APIs (NewsAPI, Alpha Vantage)
    - Twitter/X sentiment via Tweepy
    - Reddit sentiment via PRAW
    - Financial forums and blogs
    """
    
    # Legitimate financial news sources and influencers to track
    FINANCIAL_SOURCES = {
        'news': [
            'reuters.com',
            'bloomberg.com',
            'cnbc.com',
            'marketwatch.com',
            'investing.com',
            'forexlive.com',
            'fxstreet.com',
            'dailyfx.com',
            'tradingeconomics.com',
            'moneynews.com',
            'themarketear.com',
        ],
        'forex_news': [
            'forexlive.com',
            'fxstreet.com',
            'dailyfx.com',
            'oanda.com/trading/analysis',
            'investopedia.com/forex',
        ]
    }
    
    # Legitimate Twitter/X handles to track (verified financial analysts)
    TRUSTED_TWITTER_HANDLES = {
        'macro_analysts': [
            'mkborsello',           # Marcus Borsello - Macro/FX Analyst
            'ThalesAT',             # Thales A. - Macro Strategist
            'Mercmusicbox',         # Dominic Mercurio - Forex Technician
            'Cryptohopper',         # crypto influences (if trading crypto)
        ],
        'central_banks': [
            'federalreserve',
            'ecb',
            'bankofengland',
            'banxico',
            'rbanews',
        ],
        'economic_data': [
            'TradingEconomics',
            'YahooFinance',
            'MarketWatch',
            'CNBC',
            'Bloomberg',
        ]
    }
    
    # Sentiment keywords for Forex pairs
    SENTIMENT_KEYWORDS = {
        'bullish': [
            'strong', 'bullish', 'upside', 'rally', 'surge', 'gains', 'positive',
            'support', 'resistance breakout', 'breakout higher', 'upgrade', 'buy',
            'outperform', 'strength', 'robust', 'beat', 'better than expected'
        ],
        'bearish': [
            'weak', 'bearish', 'downside', 'decline', 'plunge', 'losses', 'negative',
            'resistance', 'support breakdown', 'breakdown lower', 'downgrade', 'sell',
            'underperform', 'weakness', 'soft', 'miss', 'worse than expected'
        ]
    }
    
    def __init__(self):
        """Initialize news sentiment analyzer"""
        self.sentiment_history = []
        logger.info("News Sentiment Analyzer initialized")
    
    def analyze_sentiment(self, symbol: str, timeframe_hours: int = 24) -> Dict:
        """
        Analyze sentiment from news and social media for a trading pair
        
        Args:
            symbol: Trading pair (e.g., 'EURUSD')
            timeframe_hours: Hours to look back for sentiment
        
        Returns:
            {
                'sentiment_score': float (-100 to +100),
                'sentiment_direction': str ('bullish', 'bearish', 'neutral'),
                'confidence': float (0-100),
                'sources': dict,
                'key_themes': list,
                'latest_news': list,
                'social_sentiment': dict
            }
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"📰 NEWS & SENTIMENT ANALYSIS - {symbol}")
        logger.info(f"{'='*70}")
        
        try:
            # Get sentiment from multiple sources
            news_sentiment = self._analyze_news(symbol, timeframe_hours)
            social_sentiment = self._analyze_social_media(symbol)
            
            # Combine scores (60% news, 40% social)
            combined_score = (news_sentiment['score'] * 0.6) + (social_sentiment['score'] * 0.4)
            
            # Determine direction
            if combined_score > 10:
                direction = 'bullish'
                confidence = min(100, abs(combined_score))
            elif combined_score < -10:
                direction = 'bearish'
                confidence = min(100, abs(combined_score))
            else:
                direction = 'neutral'
                confidence = 0
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'symbol': symbol,
                'sentiment_score': combined_score,
                'sentiment_direction': direction,
                'confidence': confidence,
                'news_sentiment': news_sentiment,
                'social_sentiment': social_sentiment,
                'key_themes': self._extract_themes(news_sentiment, social_sentiment),
                'recommendation': self._get_recommendation(direction, confidence)
            }
            
            self._log_sentiment_analysis(result)
            return result
        
        except Exception as e:
            logger.error(f"Error in sentiment analysis: {e}")
            return {
                'sentiment_score': 0,
                'sentiment_direction': 'neutral',
                'confidence': 0,
                'error': str(e)
            }
    
    def _analyze_news(self, symbol: str, timeframe_hours: int) -> Dict:
        """
        Analyze sentiment from financial news
        
        Returns: {
            'score': float (-100 to +100),
            'sources': dict,
            'article_count': int,
            'articles': list
        }
        """
        logger.debug(f"Fetching news for {symbol}...")
        
        # Convert symbol to currency pair (e.g., EURUSD -> EUR USD)
        base, quote = symbol[:-3], symbol[-3:]
        search_query = f"{base} {quote} forex"
        
        articles = []
        score = 0
        article_count = 0
        
        try:
            # Try NewsAPI
            articles_news_api = self._fetch_newsapi(search_query)
            articles.extend(articles_news_api)
            
            # Try Alpha Vantage
            articles_alpha = self._fetch_alpha_vantage(symbol)
            articles.extend(articles_alpha)
            
            # Calculate sentiment score from articles
            for article in articles:
                article_score = self._calculate_article_sentiment(article)
                score += article_score
                article_count += 1
            
            # Normalize score
            if article_count > 0:
                score = (score / article_count) * 100
                score = max(-100, min(100, score))
            
            return {
                'score': score,
                'article_count': article_count,
                'articles': articles[:10],  # Top 10 articles
                'sources': ['newsapi', 'alpha_vantage', 'forexlive']
            }
        
        except Exception as e:
            logger.warning(f"Could not fetch news: {e}")
            return {'score': 0, 'article_count': 0, 'articles': [], 'error': str(e)}
    
    def _fetch_newsapi(self, query: str) -> List:
        """Fetch news from NewsAPI"""
        try:
            # Note: Replace with your actual API key
            api_key = 'demo'  # Use your NewsAPI key
            url = f"https://newsapi.org/v2/everything"
            
            params = {
                'q': query,
                'sortBy': 'publishedAt',
                'language': 'en',
                'pageSize': 10,
                'apiKey': api_key
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                articles = []
                for article in data.get('articles', []):
                    articles.append({
                        'title': article['title'],
                        'description': article['description'],
                        'source': article['source']['name'],
                        'url': article['url'],
                        'published_at': article['publishedAt']
                    })
                return articles
        except Exception as e:
            logger.debug(f"NewsAPI fetch error: {e}")
        return []
    
    def _fetch_alpha_vantage(self, symbol: str) -> List:
        """Fetch news from Alpha Vantage"""
        try:
            # Note: Replace with your actual API key
            api_key = 'demo'  # Use your Alpha Vantage key
            url = "https://www.alphavantage.co/query"
            
            params = {
                'function': 'NEWS_SENTIMENT',
                'tickers': symbol,
                'apikey': api_key
            }
            
            response = requests.get(url, params=params, timeout=5)
            if response.status_code == 200:
                data = response.json()
                articles = []
                for item in data.get('feed', []):
                    articles.append({
                        'title': item['title'],
                        'description': item['summary'],
                        'source': item['source'],
                        'url': item['url'],
                        'published_at': item['time_published']
                    })
                return articles
        except Exception as e:
            logger.debug(f"Alpha Vantage fetch error: {e}")
        return []
    
    def _analyze_social_media(self) -> Dict:
        """
        Analyze sentiment from Twitter/X and Reddit
        
        Returns: {
            'score': float (-100 to +100),
            'twitter_sentiment': dict,
            'reddit_sentiment': dict,
            'tweet_count': int
        }
        """
        logger.debug("Analyzing social media sentiment...")
        
        try:
            twitter_sentiment = self._analyze_twitter()
            reddit_sentiment = self._analyze_reddit()
            
            # Combine (60% Twitter, 40% Reddit)
            combined = (twitter_sentiment['score'] * 0.6) + (reddit_sentiment['score'] * 0.4)
            
            return {
                'score': combined,
                'twitter_sentiment': twitter_sentiment,
                'reddit_sentiment': reddit_sentiment,
                'platforms': ['twitter', 'reddit']
            }
        
        except Exception as e:
            logger.debug(f"Social media analysis error: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _analyze_twitter(self) -> Dict:
        """Analyze Twitter/X sentiment"""
        # Note: Requires tweepy library - pip install tweepy
        try:
            import tweepy
            
            # Configure with your Twitter API credentials
            # This is a placeholder - implement with real credentials
            client = None  # Initialize with real credentials
            
            if client is None:
                logger.warning("Twitter API not configured")
                return {'score': 0, 'tweets': [], 'error': 'Not configured'}
            
            # Search for recent tweets about forex/currency
            tweet_score = 0
            tweet_count = 0
            
            # In real implementation:
            # tweets = client.search_recent_tweets(query="EURUSD", max_results=100)
            # Calculate sentiment...
            
            return {
                'score': tweet_score,
                'tweet_count': tweet_count,
                'trend': 'neutral'
            }
        
        except ImportError:
            logger.debug("Tweepy not installed. Install with: pip install tweepy")
            return {'score': 0, 'error': 'Tweepy not installed'}
        except Exception as e:
            logger.debug(f"Twitter analysis error: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _analyze_reddit(self) -> Dict:
        """Analyze Reddit sentiment"""
        # Note: Requires praw library - pip install praw
        try:
            import praw
            
            # Configure with your Reddit API credentials
            reddit = None  # Initialize with real credentials
            
            if reddit is None:
                logger.warning("Reddit API not configured")
                return {'score': 0, 'posts': [], 'error': 'Not configured'}
            
            # Search relevant subreddits
            post_score = 0
            post_count = 0
            
            # In real implementation:
            # subreddits = ['Forex', 'investing', 'stocks']
            # Calculate sentiment from posts...
            
            return {
                'score': post_score,
                'post_count': post_count,
                'trend': 'neutral'
            }
        
        except ImportError:
            logger.debug("PRAW not installed. Install with: pip install praw")
            return {'score': 0, 'error': 'PRAW not installed'}
        except Exception as e:
            logger.debug(f"Reddit analysis error: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _calculate_article_sentiment(self, article: Dict) -> float:
        """Calculate sentiment score for a single article (-1 to +1)"""
        text = (article.get('title', '') + ' ' + article.get('description', '')).lower()
        
        bullish_count = sum(1 for keyword in self.SENTIMENT_KEYWORDS['bullish'] if keyword in text)
        bearish_count = sum(1 for keyword in self.SENTIMENT_KEYWORDS['bearish'] if keyword in text)
        
        if bullish_count + bearish_count == 0:
            return 0
        
        return (bullish_count - bearish_count) / (bullish_count + bearish_count)
    
    def _extract_themes(self, news_sentiment: Dict, social_sentiment: Dict) -> List:
        """Extract key themes from sentiment analysis"""
        themes = []
        
        if news_sentiment.get('article_count', 0) > 0:
            themes.append(f"Strong media coverage ({news_sentiment['article_count']} articles)")
        
        if abs(news_sentiment.get('score', 0)) > 30:
            themes.append(f"Clear news bias: {news_sentiment['score']:.0f} points")
        
        return themes
    
    def _get_recommendation(self, direction: str, confidence: float) -> str:
        """Get trading recommendation based on sentiment"""
        if confidence < 20:
            return "Insufficient sentiment data"
        elif direction == 'bullish' and confidence > 60:
            return "Strong bullish bias - consider buying on dips"
        elif direction == 'bearish' and confidence > 60:
            return "Strong bearish bias - consider selling on rallies"
        else:
            return "Mixed sentiment - use technical confirmation"
    
    def _log_sentiment_analysis(self, result: Dict):
        """Log sentiment analysis results"""
        logger.info(f"\nSentiment: {result['sentiment_direction'].upper()}")
        logger.info(f"Score: {result['sentiment_score']:+.1f}")
        logger.info(f"Confidence: {result['confidence']:.1f}%")
        logger.info(f"Recommendation: {result['recommendation']}")


# ==================== FUNDAMENTAL ANALYSIS ====================

class FundamentalAnalyzer:
    """
    Analyzes fundamental factors affecting currency pairs
    Includes:
    - COT (Commitments of Traders) reports
    - Economic calendar events
    - Central bank decisions and guidance
    - Interest rate differentials
    - Economic indicators (GDP, inflation, employment)
    """
    
    # Currency pair fundamentals mapping
    PAIR_FUNDAMENTALS = {
        'EURUSD': {
            'base': 'EUR',
            'quote': 'USD',
            'base_country': 'Eurozone',
            'quote_country': 'United States',
            'key_events': ['ECB interest rate', 'US employment', 'inflation data'],
            'interest_diff': 'USD rates - EUR rates'
        },
        'GBPUSD': {
            'base': 'GBP',
            'quote': 'USD',
            'base_country': 'United Kingdom',
            'quote_country': 'United States',
            'key_events': ['BoE interest rate', 'US employment', 'UK inflation']
        },
        'USDJPY': {
            'base': 'USD',
            'quote': 'JPY',
            'base_country': 'United States',
            'quote_country': 'Japan',
            'key_events': ['US employment', 'Fed interest rate', 'BoJ policy']
        },
        'AUDUSD': {
            'base': 'AUD',
            'quote': 'USD',
            'base_country': 'Australia',
            'quote_country': 'United States',
            'key_events': ['RBA interest rate', 'China growth', 'US data']
        }
    }
    
    def __init__(self):
        """Initialize fundamental analyzer"""
        logger.info("Fundamental Analyzer initialized")
    
    def get_fundamental_score(self, symbol: str) -> Dict:
        """
        Calculate fundamental score for a trading pair
        
        Args:
            symbol: Trading pair (e.g., 'EURUSD')
        
        Returns:
            {
                'fundamental_score': float (-100 to +100),
                'fundamental_direction': str,
                'cot_signal': dict,
                'interest_rate_diff': dict,
                'economic_events': list,
                'key_factors': dict,
                'outlook': str
            }
        """
        logger.info(f"\n{'='*70}")
        logger.info(f"📊 FUNDAMENTAL ANALYSIS - {symbol}")
        logger.info(f"{'='*70}")
        
        try:
            # Get all fundamental components
            cot_signal = self._analyze_cot_report(symbol)
            interest_diff = self._get_interest_rate_differential(symbol)
            upcoming_events = self._get_economic_calendar(symbol)
            macro_factors = self._get_macro_factors(symbol)
            
            # Calculate combined fundamental score
            components = [
                ('COT', cot_signal.get('score', 0), 0.35),
                ('Interest Rates', interest_diff.get('score', 0), 0.30),
                ('Macro Factors', macro_factors.get('score', 0), 0.25),
                ('Economic Events', upcoming_events.get('score', 0), 0.10)
            ]
            
            total_score = sum(score * weight for _, score, weight in components)
            
            # Determine direction
            if total_score > 10:
                direction = 'bullish'
            elif total_score < -10:
                direction = 'bearish'
            else:
                direction = 'neutral'
            
            result = {
                'symbol': symbol,
                'fundamental_score': total_score,
                'fundamental_direction': direction,
                'components': {name: {'score': score, 'weight': f'{weight*100:.0f}%'} 
                              for name, score, weight in components},
                'cot_signal': cot_signal,
                'interest_rate_diff': interest_diff,
                'upcoming_events': upcoming_events[:5],  # Next 5 events
                'macro_factors': macro_factors,
                'outlook': self._generate_outlook(total_score, symbol)
            }
            
            self._log_fundamental_analysis(result)
            return result
        
        except Exception as e:
            logger.error(f"Error in fundamental analysis: {e}")
            return {
                'fundamental_score': 0,
                'fundamental_direction': 'neutral',
                'error': str(e)
            }
    
    def _analyze_cot_report(self, symbol: str) -> Dict:
        """
        Analyze COT (Commitments of Traders) report
        Shows positioning of large traders (commercial, non-commercial, small speculators)
        """
        logger.debug(f"Analyzing COT report for {symbol}...")
        
        # COT data is typically available from CFTC
        # For demo, using sample structure
        
        try:
            # In real implementation, fetch from CFTC or financial APIs
            # https://www.cftc.gov/MarketReports/CommitmentsofTraders/
            
            cot_data = {
                'commercial_positions': {'long': 0, 'short': 0, 'net': 0},
                'non_commercial_positions': {'long': 0, 'short': 0, 'net': 0},
                'small_trader_positions': {'long': 0, 'short': 0, 'net': 0},
                'last_update': datetime.now().isoformat(),
                'extreme_positioning': False
            }
            
            # Calculate COT signal
            # Positive: Commercial short, Non-commercial long (bullish)
            # Negative: Commercial long, Non-commercial short (bearish)
            
            cot_score = self._calculate_cot_score(cot_data)
            
            return {
                'score': cot_score,
                'data': cot_data,
                'signal': 'bullish' if cot_score > 0 else 'bearish' if cot_score < 0 else 'neutral',
                'extreme': cot_data['extreme_positioning']
            }
        
        except Exception as e:
            logger.warning(f"COT analysis error: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _calculate_cot_score(self, cot_data: Dict) -> float:
        """Calculate COT score (-100 to +100)"""
        # This is a simplified scoring system
        # In real implementation, use more sophisticated analysis
        return 0.0
    
    def _get_interest_rate_differential(self, symbol: str) -> Dict:
        """
        Get interest rate differential between two currencies
        This is a major driver of carry trade sentiment
        """
        logger.debug(f"Analyzing interest rate differential for {symbol}...")
        
        try:
            # Current interest rates (update as needed)
            interest_rates = {
                'USD': 5.33,      # Federal Reserve
                'EUR': 4.25,      # ECB
                'GBP': 5.25,      # BoE
                'JPY': -0.10,     # BoJ
                'AUD': 4.35,      # RBA
                'CAD': 5.00,      # BoC
                'CHF': 1.75,      # SNB
                'NZD': 5.50,      # RBNZ
            }
            
            fund_info = self.PAIR_FUNDAMENTALS.get(symbol, {})
            base_ccy = fund_info.get('base', symbol[:3])
            quote_ccy = fund_info.get('quote', symbol[3:])
            
            base_rate = interest_rates.get(base_ccy, 0)
            quote_rate = interest_rates.get(quote_ccy, 0)
            
            # Rate differential (positive = quote currency attractive)
            rate_diff = quote_rate - base_rate
            
            # Score: each 1% difference = ~10 points
            score = rate_diff * 10
            score = max(-100, min(100, score))
            
            return {
                'score': score,
                'base_currency': base_ccy,
                'base_rate': base_rate,
                'quote_currency': quote_ccy,
                'quote_rate': quote_rate,
                'differential': rate_diff,
                'signal': 'bullish' if rate_diff > 0 else 'bearish' if rate_diff < 0 else 'neutral'
            }
        
        except Exception as e:
            logger.warning(f"Interest rate analysis error: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _get_economic_calendar(self, symbol: str) -> Dict:
        """
        Get upcoming economic calendar events for the currency pair
        High impact events can cause significant price movements
        """
        logger.debug(f"Fetching economic calendar for {symbol}...")
        
        try:
            # Sample upcoming events structure
            # In real implementation, fetch from TradingEconomics, Investing.com, or Bloomberg
            
            events = [
                {
                    'date': datetime.now() + timedelta(hours=2),
                    'country': 'US',
                    'event': 'Non-Farm Payroll',
                    'importance': 'HIGH',
                    'forecast': 200000,
                    'previous': 180000,
                    'currency': 'USD'
                },
                {
                    'date': datetime.now() + timedelta(hours=6),
                    'country': 'Eurozone',
                    'event': 'CPI Inflation',
                    'importance': 'HIGH',
                    'forecast': 2.1,
                    'previous': 2.3,
                    'currency': 'EUR'
                }
            ]
            
            # Filter for relevant currencies
            fund_info = self.PAIR_FUNDAMENTALS.get(symbol, {})
            relevant_events = [e for e in events if e['currency'] in symbol]
            
            # Score based on events
            score = 0
            for event in relevant_events:
                if event['importance'] == 'HIGH':
                    score += 5
                elif event['importance'] == 'MEDIUM':
                    score += 2
            
            return {
                'score': min(100, score * 5),
                'upcoming_events': relevant_events,
                'event_count': len(relevant_events),
                'high_impact_soon': any(e['importance'] == 'HIGH' and 
                                       e['date'] < datetime.now() + timedelta(hours=4) 
                                       for e in relevant_events)
            }
        
        except Exception as e:
            logger.warning(f"Economic calendar error: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _get_macro_factors(self, symbol: str) -> Dict:
        """
        Analyze macro factors (GDP growth, inflation, employment, etc.)
        """
        logger.debug(f"Analyzing macro factors for {symbol}...")
        
        try:
            # Sample macro data (update with real data)
            macro_factors = {
                'USD': {
                    'gdp_growth': 2.5,
                    'inflation': 3.2,
                    'unemployment': 3.8,
                    'fed_funds_rate': 5.33,
                    'outlook': 'neutral'
                },
                'EUR': {
                    'gdp_growth': 0.5,
                    'inflation': 2.1,
                    'unemployment': 6.5,
                    'ecb_rate': 4.25,
                    'outlook': 'neutral'
                }
            }
            
            fund_info = self.PAIR_FUNDAMENTALS.get(symbol, {})
            base_ccy = fund_info.get('base', symbol[:3])
            quote_ccy = fund_info.get('quote', symbol[3:])
            
            base_macro = macro_factors.get(base_ccy, {})
            quote_macro = macro_factors.get(quote_ccy, {})
            
            # Simple scoring: stronger economy = bullish for that currency
            score = 0
            
            if base_macro.get('gdp_growth', 0) > quote_macro.get('gdp_growth', 0):
                score += 15
            if quote_macro.get('inflation', 0) > base_macro.get('inflation', 0):
                score += 10
            
            return {
                'score': max(-100, min(100, score)),
                'base_currency': base_macro,
                'quote_currency': quote_macro,
                'analysis': f"Economic comparison between {base_ccy} and {quote_ccy}"
            }
        
        except Exception as e:
            logger.warning(f"Macro analysis error: {e}")
            return {'score': 0, 'error': str(e)}
    
    def _generate_outlook(self, score: float, symbol: str) -> str:
        """Generate text outlook based on fundamental score"""
        if score > 30:
            return f"Strong fundamental support for {symbol} upside"
        elif score > 10:
            return f"Moderate fundamental support for {symbol} upside"
        elif score < -30:
            return f"Strong fundamental support for {symbol} downside"
        elif score < -10:
            return f"Moderate fundamental support for {symbol} downside"
        else:
            return f"Mixed fundamentals for {symbol}, watch key economic releases"
    
    def _log_fundamental_analysis(self, result: Dict):
        """Log fundamental analysis results"""
        logger.info(f"\nFundamental Score: {result['fundamental_score']:+.1f}")
        logger.info(f"Direction: {result['fundamental_direction'].upper()}")
        logger.info(f"Outlook: {result['outlook']}")
        
        if result.get('components'):
            logger.info("\nComponent Scores:")
            for name, data in result['components'].items():
                logger.info(f"  {name}: {data['score']:+.1f} ({data['weight']})")


# ==================== COMBINED ANALYSIS FUNCTION ====================

def get_combined_sentiment_fundamental_score(symbol: str) -> Dict:
    """
    Get combined sentiment and fundamental score for a symbol
    
    Args:
        symbol: Trading pair (e.g., 'EURUSD')
    
    Returns:
        {
            'overall_score': float (-100 to +100),
            'overall_direction': str ('bullish', 'bearish', 'neutral'),
            'sentiment_analysis': dict,
            'fundamental_analysis': dict,
            'combined_signal': str,
            'confidence': float (0-100)
        }
    """
    logger.info("\n" + "="*70)
    logger.info(f"🔄 COMBINED SENTIMENT & FUNDAMENTAL ANALYSIS - {symbol}")
    logger.info("="*70)
    
    try:
        # Get sentiment and fundamental scores
        news_analyzer = NewsSentimentAnalyzer()
        sentiment_result = news_analyzer.analyze_sentiment(symbol)
        
        fund_analyzer = FundamentalAnalyzer()
        fundamental_result = fund_analyzer.get_fundamental_score(symbol)
        
        # Combine scores (60% fundamental, 40% sentiment)
        overall_score = (
            (fundamental_result.get('fundamental_score', 0) * 0.6) +
            (sentiment_result.get('sentiment_score', 0) * 0.4)
        )
        
        # Determine overall direction
        if overall_score > 15:
            overall_direction = 'bullish'
        elif overall_score < -15:
            overall_direction = 'bearish'
        else:
            overall_direction = 'neutral'
        
        # Calculate confidence
        sentiment_conf = sentiment_result.get('confidence', 0)
        fundamental_score_abs = abs(fundamental_result.get('fundamental_score', 0))
        fundamental_conf = min(100, fundamental_score_abs)
        combined_confidence = (sentiment_conf * 0.4) + (fundamental_conf * 0.6)
        
        # Generate combined signal
        if overall_direction == 'bullish' and combined_confidence > 60:
            combined_signal = 'Strong BUY signal'
        elif overall_direction == 'bullish':
            combined_signal = 'Moderate BUY signal'
        elif overall_direction == 'bearish' and combined_confidence > 60:
            combined_signal = 'Strong SELL signal'
        elif overall_direction == 'bearish':
            combined_signal = 'Moderate SELL signal'
        else:
            combined_signal = 'NEUTRAL - No clear macro bias'
        
        result = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'overall_score': overall_score,
            'overall_direction': overall_direction,
            'combined_signal': combined_signal,
            'confidence': combined_confidence,
            'sentiment_analysis': sentiment_result,
            'fundamental_analysis': fundamental_result,
            'alignment': 'Sentiment and Fundamentals ALIGNED' if (
                (sentiment_result.get('sentiment_direction') == fundamental_result.get('fundamental_direction'))
            ) else 'Sentiment and Fundamentals DIVERGENT',
            'recommendation': _get_macro_recommendation(overall_direction, combined_confidence)
        }
        
        _log_combined_analysis(result)
        return result
    
    except Exception as e:
        logger.error(f"Error in combined analysis: {e}", exc_info=True)
        return {
            'overall_score': 0,
            'overall_direction': 'neutral',
            'combined_signal': 'Error in analysis',
            'confidence': 0,
            'error': str(e)
        }


def _get_macro_recommendation(direction: str, confidence: float) -> str:
    """Get trading recommendation based on macro analysis"""
    if confidence < 30:
        return "Insufficient macro signal - rely on technical analysis"
    elif direction == 'bullish' and confidence > 70:
        return "STRONG macro support for longs - prioritize buy setups"
    elif direction == 'bullish' and confidence > 50:
        return "MODERATE macro support for longs - consider bias"
    elif direction == 'bearish' and confidence > 70:
        return "STRONG macro support for shorts - prioritize sell setups"
    elif direction == 'bearish' and confidence > 50:
        return "MODERATE macro support for shorts - consider bias"
    else:
        return "Mixed macro signals - await clearer setup"


def _log_combined_analysis(result: Dict):
    """Log combined analysis results"""
    logger.info("\n" + "="*70)
    logger.info("📊 COMBINED MACRO ANALYSIS SUMMARY")
    logger.info("="*70)
    logger.info(f"Overall Score: {result['overall_score']:+.1f}")
    logger.info(f"Direction: {result['overall_direction'].upper()}")
    logger.info(f"Signal: {result['combined_signal']}")
    logger.info(f"Confidence: {result['confidence']:.1f}%")
    logger.info(f"Alignment: {result['alignment']}")
    logger.info(f"Recommendation: {result['recommendation']}")
    logger.info("="*70 + "\n")