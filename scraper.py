import re
import nltk
import hashlib
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from urllib.parse import urlparse
from collections import defaultdict
from collections import OrderedDict
nltk.download('punkt')

Blacklist = set()
Visited = set()
Robots_txt = {}
Simhashes = list()
Stop_Words = {"a", "about", "above", "after", "again", "against", "all", "am",
    "an", "and", "any", "are", "aren't", "as", "at", "be", "because", "been", 
    "before", "being", "below", "between", "both", "but", "by", "can't", 
    "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", 
    "doing", "don't", "down", "during", "each", "few", "for", "from", 
    "further", "had", "hadn't", "has", "hasn't", "have", "haven't", "having", 
    "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers", "herself", 
    "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", 
    "i've", "if", "in", "into", "is", "isn't", "it", "it's", "its", "itself",
    "let's", "me", "more", "most", "mustn't", "my", "myself", "no", "nor", 
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", 
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", 
    "she'd", "she'll", "she's", "should", "shouldn't", "so", "some", "such", 
    "than", "that", "that's", "the", "their", "theirs", "them", "themselves", 
    "then", "there", "there's", "these", "they", "they'd", "they'll", 
    "they're", "they've", "this", "those", "through", "to", "too", "under", 
    "until", "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", 
    "we've", "were", "weren't", "what", "what's", "when", "when's", "where", 
    "where's", "which", "while", "who", "who's", "whom", "why", "why's", 
    "with", "won't", "would", "wouldn't", "you", "you'd", "you'll", "you're", 
    "you've", "your", "yours", "yourself", "yourselves"}
Longest_Page = ('Default', 0)
Common_Words = defaultdict(int)
Subdomain = defaultdict(int) # {key = Subdomains under ics.uci.edu domain, value = a counter of unique Pages}

#writes to txt file, the current 50 most common words
def common_words_write():
    global Common_Words
    with open("common_words_log.txt", "w") as f:
        file_string = ''
        for count, kv in enumerate(sorted(Common_Words.items(), key=(lambda x: x[1]), reverse=True)[:50]):
            file_string += f'{count+1:02}. {kv[0]} - {kv[1]}\n'
        f.write(file_string)

#writes to a txt file the longest page along with its word count
def longest_page_write():
    global Longest_Page
    with open("longest_page_log.txt", "w") as f:
        f.write(f'(Word-Count = {Longest_Page[1]}; URL = {Longest_Page[0]})\n')

#writes to txt file the current subdomain list
def subdomain_list_write():
    global Subdomain
    with open("subdomain_list.txt", "w") as f:
        file_string = ''
        for kv in sorted(Subdomain):
            file_string += f'{kv}, {Subdomain[kv]}\n'
        f.write(file_string)

#this will update subdomain dict per url
#we do not need to check for unique url because it is used in extract_next_links
def subdomain_update(url):
    global Subdomain
    if(url.find(".ics.uci.edu") == -1):
        return
    pattern = 'https?://(.*)\.ics\.uci\.edu'
    subdomain_str = re.search(pattern, url).group(1)
    Subdomain['http://' + subdomain_str + '.ics.uci.edu'] +=1

def scraper(url, resp) -> list:
    links = extract_next_links(url, resp)
    valid_links = [link for link in links if is_valid(link)]
    if resp.status == 200:
        word_token_list = tokenize_response(resp)       # gather all tokens from webpage
        check_longest_page(url, len(word_token_list))   # check if Longest_Page needs to be updated
        compute_word_frequencies(word_token_list)       # find frequencies of each token and insert into Common_Words
        
        common_words_write()
        longest_page_write()
        subdomain_list_write()
    return valid_links

# get data from website and tokenize it taking out everything that isn't a word
def tokenize_response(resp):
    soup = BeautifulSoup(resp.raw_response.content, "html.parser")
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
    global Blacklist, Visited, Robots_txt, Simhashes

    # If status is bad or link already visited add it to a blacklist to avoid
    if resp.status != 200 or url in Blacklist or url in Visited:
        Blacklist.add(url)
        return set()

    subdomain_update(url) #added here so we can avoid checking if unique

    # If tokens < 100 dont continue checking link
    if wordcount_check(resp):
        Blacklist.add(url)
        return set()

    # Create fingerprint for page
    simhash = create_simhash(resp)

    # If exact simhash is already stored we've already crawled a copy of this page
    if simhash in Simhashes:
        Blacklist.add(url)
        return set()
    # Else check for similarity in all stored simhashes
    # If threshold > 0.95 the page is too similar and we should blacklist
    # and skip
    else:
        try:
            sim = max(similarity(simhash, s) for s in Simhashes)
            if sim >= 0.95:
                Simhashes.append(simhash)
                Blacklist.add(url)
                return set()
        except ValueError:
            Simhashes.append(simhash)

    if simhash not in Simhashes:
        Simhashes.append(simhash)

    nextLinks = set()

    soup = BeautifulSoup(resp.raw_response.content, "html.parser")

    for link in soup.find_all('a'):
        href = link.attrs.get('href')

        # If link is relative make it absolute
        if urlparse(url).netloc:
            href = urljoin(url, href)

        # Stop duplicates of same link by splitting
        # (ex #ref40, #ref45 etc of same link)
        # not sure if including '?' is necessary, need further testing
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

    path = parsed.path
    netloc = parsed.netloc
    check = 0

    # Make sure URL is in provided domain constraints
    if ".ics.uci.edu" not in netloc:
        check +=1
    if ".cs.uci.edu" not in netloc:
        check +=1
    if ".informatics.uci.edu" not in netloc:
        check +=1
    if ".stat.uci.edu" not in netloc:
        check +=1
    if ".today.uci.edu" not in netloc:
        check +=1

    # Jank but it works, if check != 4 then one of the strings was not 
    # present inside of the provided URL
    if check != 4:
        return False

    if ".today.uci.edu" in parsed.netloc and "/department/information_computer_sciences/" not in parsed.path:
        return False

    # files and papers both have links of documents
    # not sure if useful to exclude or not yet, more testing
    if "/files/" in parsed.path:
        return False
    if "/papers/" in parsed.path:
        return False

    # Regex expression to not allow repeating directories
    # Source: https://support.archive-it.org/hc/en-us/articles/208332963-Modify-crawl-scope-with-a-Regular-Expression
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
            + r"|img|sql|odc|txt|war|apk|mpg|scm|ps.Z|rss|c|tex.Z|bib.Z|pps|bib|ppsx)$", parsed.path.lower()):
            # .bib? 
        return False
    return True

# Calculate similarity between two webpages
def similarity(hash1, hash2):
    return sum(h1 == h2 for h1, h2 in zip(hash1, hash2)) / 160

def create_simhash(resp):
    #tokenize
    tokens = tokenize_response(resp)

    # convert to dictionary with frequency sorted by key
    freq = defaultdict(int)
    for t in tokens:
        freq[t] += 1
    sortFreq = OrderedDict(sorted(freq.items(), key=lambda kv: kv[1], reverse=True))

    # get set of keys to convert to hex and store in list
    wordList = list(sortFreq.keys())

    hashList = list()
    binList = list()

    # Convert each word to hex and store
    for word in wordList:
        hashList.append(hashlib.sha1(word.encode()).hexdigest())

    # Convert each hex into 160 bit binary string and store
    for h in hashList:
        binary = bin(int(h, 16))
        binList.append(binary[2:].zfill(160))
    
    weightList = list()

    # Calculate overall weight of each bit position and store
    for pos in reversed(range(160)):
        num = 0
        i = 0
        for binNum in binList:
            # get weight
            weight = sortFreq[wordList[i]]
            # get binary bit
            binary = binNum[pos]
            # adjust weight for position according to binary bit
            num += weight if binary == '1' else -weight
            i += 1
    
        weightList.append(num)

    #convert from weightList to the simhash
    simhash = list()
    for w in weightList:
        if w >= 0:
            simhash.append(1)
        else:
            simhash.append(0)

    # Take the simash in list and return as string
    simStr = [str(int) for int in simhash]
    finalHash = ''.join(simStr)
    return(finalHash)


# Return True (to enter into if statement to skip link) 
# if token count less than 100
def wordcount_check(resp):
    word_tokens = tokenize_response(resp)
    if len(word_tokens) < 100:
        return True
    return False

'''
def robots_check(resp, parsed):
    try:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url('http://' + parsed.netloc + '/robots.txt')
        rp.read()
        return rp.can_fetch("*", netloc)
    except:
        return False
'''