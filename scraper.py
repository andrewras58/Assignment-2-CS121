import re
from urllib.parse import urlparse
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from collections import defaultdict
import nltk
nltk.download('punkt')

Blacklist = set()
Visited = set()
Stop_Words = {"a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs", "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're", "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's", "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself", "yourselves"}
Longest_Page = ('Default', 0)
Common_Words = defaultdict(int)

#writes to txt file, the current 50 most common words
def common_words_write():
    global Common_Words
    with open("common_words_log.txt", "w") as f:
        file_string = ''
        for count, kv in enumerate(sorted(Common_Words.items(), key=(lambda x: x[1]), reverse=True)[:50]):
            file_string += f'{count+1:02}. (Word = {kv[0]}, Word-Count = {kv[1]})\n'
        f.write(file_string)

#writes to a txt file the longest page along with its word count
def longest_page_write():
    global Longest_Page
    with open("longest_page_log.txt", "w") as f:
        f.write(f'(Word-Count = {Longest_Page[1]}; URL = {Longest_Page[0]})\n')

def unique_pages_write():
    return

def scraper(url, resp) -> list:
    links = extract_next_links(url, resp)
    valid_links = [link for link in links if is_valid(link)]
    if resp.status == 200:
        word_token_list = tokenize_response(resp)       # gather all tokens from webpage
        check_longest_page(url, len(word_token_list))   # check if Longest_Page needs to be updated
        compute_word_frequencies(word_token_list)       # find frequencies of each token and insert into Common_Words
        #print(Common_Words)
        #print(Longest_Page)
        common_words_write()
        longest_page_write()
    return valid_links

# get data from website and tokenize it taking out everything that isn't a word
def tokenize_response(resp):
    content = resp.raw_response.content
    soup = BeautifulSoup(content, "html.parser")
    tokens = nltk.tokenize.word_tokenize(soup.get_text()) # uses nltk to tokenize webpage
    word_tokens = [t for t in tokens if not re.match(r'[\W]+', t)]
    return word_tokens

# assign new value to Longest_Page if current page is longer
def check_longest_page(url, page_len):
    global Longest_Page
    if Longest_Page[1] < page_len:
        Longest_Page = (url, page_len)

# increment word count in Common_Words for all words found on this page
def compute_word_frequencies(tokens):
    # for loop which adds count to Common_Words dictionary
    global Common_Words, Stop_Words
    for token in tokens:
        if token not in Stop_Words:
            Common_Words[token] += 1

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    global Blacklist, Visited

    # If status is bad or link already visited add it to a blacklist to avoid
    if resp.status != 200 or url in Blacklist or url in Visited:
        Blacklist.add(url)
        return set()

    nextLinks = set()

    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
    for link in soup.find_all('a'):
        href = link.attrs.get('href')

        # If link is relative make it absolute
        if urlparse(url).netloc:
            href = urljoin(url, href)

        # Stop duplicates of same link by splitting
        # (ex #ref40, #ref45 etc of same link)
        # not sure if including '?' is necessary, neef further testing
        href = href.split('#')[0]
        href = href.split('?')[0]

        if is_valid(href):
            nextLinks.add(href)

    # Add current url to list of visited urls so we don't end up visiting already visited links
    parsed = urlparse(url)
    Visited.add(parsed.scheme + '://' + parsed.netloc + parsed.path)
    return nextLinks

def is_valid(url):
    # Decide whether to crawl this url or not.
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    global Blacklist, Visited

    if url in Visited or url in Blacklist:
        return False

    try:
        parsed = urlparse(url)
    except TypeError:
        print(f'TypeError for {url}')
        raise

    if parsed.scheme not in {"http", "https"}:
        return False

    # Make sure link is in provided domain constraints
    if parsed.netloc not in {"www.ics.uci.edu", "www.cs.uci.edu", "www.informatics.uci.edu", "www.stat.uci.edu", "www.today.uci.edu"}:
        return False

    if parsed.netloc == "www.today.uci.edu" and parsed.path != "/department/information_computer_sciences/":
        return False

    # Regex expression to not allow repeating directories
    # Source: https://support.archive-it.org/hc/en-us/articles/208332963-Modify-crawl-scope-with-a-Regular-Expression
    # Note: Not yet sure if this is working or not, will need more testing
    # Seems to work better with 'r' than without (or work in general, not sure)
    if re.match(r"^.*?(/.+?/).*?\1.*$|^.*?/(.+?/)\2.*$", parsed.path):
        return False

    if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz"
            # Added
            + r"img|sql)$", parsed.path.lower()):
        return False
    return True

# Binary search to find the 2 most similar hashes in a sorted list
# Code edited from: https://www.tutorialspoint.com/python-program-to-implement-binary-search-without-recursion
def search_hashes(hashes: [int], query: int) -> (int, int):
    low = 0
    high = len(hashes) - 1
    while low <= high:
        mid = (high + low) // 2
        if hashes[mid] < query:
            low = mid + 1
        elif hashes[mid] > query:
            high = mid - 1
    return hashes[low], hashes[high]

# checks to see how similar the number is and returns True or False based on a given threshold
def hash_similarity(query: int, sim_pair: (int, int), threshold: float) -> bool:
    return 1-abs(sim_pair[0]-query)/query > threshold or 1-abs(sim_pair[1]-query)/query > threshold

# A modified version of selection sort that only puts the newest element where it needs to be
# Code edited from: https://www.geeksforgeeks.org/python-program-for-insertion-sort/
def insert_to_hashes(hashes: [int], new_hash: int) -> None:
    hashes.append(new_hash)
    i = len(hashes) - 1
    j = i - 1
    key = hashes[i]
    while j >= 0 and key < hashes[j]:
        hashes[j+1] = hashes[j]
        j -= 1
    hashes[j+1] = key
