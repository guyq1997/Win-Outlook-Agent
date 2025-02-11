import argparse
import sys
import time
from duckduckgo_search import DDGS
from loguru import logger
def search_with_retry(query, max_results=10, max_retries=3):
    """
    Search using DuckDuckGo and return results with URLs and text snippets.
    
    Args:
        query (str): Search query
        max_results (int): Maximum number of results to return
        max_retries (int): Maximum number of retry attempts
    """
    for attempt in range(max_retries):
        try:
            print(f"DEBUG: Searching for query: {query} (attempt {attempt + 1}/{max_retries})", 
                  file=sys.stderr)
            
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
                
            if not results:
                print("DEBUG: No results found", file=sys.stderr)
                return []
            
            print(f"DEBUG: Found {len(results)} results", file=sys.stderr)
            return results
                
        except Exception as e:
            print(f"ERROR: Attempt {attempt + 1}/{max_retries} failed: {str(e)}", file=sys.stderr)
            if attempt < max_retries - 1:  # If not the last attempt
                print(f"DEBUG: Waiting 1 second before retry...", file=sys.stderr)
                time.sleep(1)  # Wait 1 second before retry
            else:
                print(f"ERROR: All {max_retries} attempts failed", file=sys.stderr)
                raise

def format_results(results):
    """Format and print search results."""
    final_results = ""
    for i, r in enumerate(results, 1):
        final_results += f"\n=== Result {i} ===\n"
        final_results += f"URL: {r.get('href', 'N/A')}\n"
        final_results += f"Title: {r.get('title', 'N/A')}\n"
        final_results += f"Snippet: {r.get('body', 'N/A')}\n"
        final_results += f"-----------------------------------\n"
    #logger.info(f"Final results: {final_results}")
    return final_results


def search(query, max_results=10, max_retries=3):
    """
    Search in the internet with retry mechanism.
    
    Args:
        query (str): Search query
        max_results (int): Maximum number of results to return
        max_retries (int): Maximum number of retry attempts
    """
    try:
        results = search_with_retry(query, max_results, max_retries)
        if results:
            return format_results(results)
            
    except Exception as e:
        print(f"ERROR: Search failed: {str(e)}", file=sys.stderr)
        sys.exit(1)