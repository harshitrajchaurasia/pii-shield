"""
PI Remover Dictionaries Module.

Contains name dictionaries, company names, and internal system names
used for PI detection.

These can be extended by loading external files at runtime.

Usage:
    from pi_remover.dictionaries import (
        INDIAN_FIRST_NAMES,
        INDIAN_LAST_NAMES,
        COMPANY_NAMES,
        INTERNAL_SYSTEMS,
    )
"""

from typing import Set


# ============================================================================
# Common Indian First Names (expandable)
# ============================================================================

INDIAN_FIRST_NAMES: Set[str] = {
    # Male names
    "aakash", "aarav", "abhay", "abhijit", "abhilash", "abhinav", "abhishek",
    "aditya", "ajay", "ajit", "akash", "akhil", "akshay", "alok", "aman",
    "amit", "amitabh", "amol", "anand", "aniket", "anil", "anirudh", "anjali",
    "ankur", "anmol", "anshul", "anuj", "anupam", "aravind", "arjun", "arun",
    "arvind", "ashish", "ashok", "ashwin", "balaji", "bhaskar", "bhavesh",
    "chandan", "chandresh", "chirag", "darshan", "deepak", "dev", "devendra",
    "dhananjay", "dhruv", "dilip", "dinesh", "gaurav", "gautam", "girish",
    "gopal", "govind", "hari", "harish", "hemant", "hitesh", "ishaan",
    "jagdish", "jai", "jayant", "jayesh", "jitendra", "karan", "kartik",
    "keshav", "kishore", "krishna", "kumar", "lalit", "lokesh", "madhav",
    "mahesh", "manoj", "manish", "mayank", "milan", "mohit", "mukesh",
    "nandan", "naresh", "naveen", "nikhil", "nilesh", "niraj", "nishant",
    "om", "pankaj", "paras", "parth", "pavan", "prakash", "pramod", "pranav",
    "prashant", "pratik", "praveen", "priyank", "rahul", "raj", "rajat",
    "rajeev", "rajesh", "rajiv", "rakesh", "ramesh", "ravi", "rohit", "sachin",
    "sagar", "sahil", "sameer", "sandeep", "sanjay", "sanjiv", "santosh",
    "satish", "shailesh", "shashank", "shekhar", "shivam", "shubham", "siddharth",
    "sudhir", "sumit", "sundar", "sunil", "suraj", "suresh", "tanmay", "tarun",
    "tushar", "uday", "umesh", "vaibhav", "varun", "vijay", "vikas", "vikram",
    "vinay", "vineet", "vinod", "vipin", "vishal", "vivek", "yash", "yogesh",
    # Female names
    "aishwarya", "akshata", "amrita", "ananya", "anju", "ankita", "anushka",
    "anusha", "aparna", "archana", "arti", "asha", "bhavna", "chitra",
    "deepa", "deepika", "devika", "diya", "divya", "ekta", "garima", "gayatri",
    "geeta", "harini", "hema", "isha", "ishita", "jaya", "jyoti", "kajal",
    "kamala", "kanchan", "kavita", "keya", "khushi", "kiran", "komal", "kriti",
    "lakshmi", "lata", "laxmi", "madhu", "mamta", "manisha", "meena", "meera",
    "megha", "menaka", "mira", "mohini", "nandini", "neelam", "neeta", "neha",
    "nidhi", "nisha", "nita", "pallavi", "payal", "pooja", "poonam", "prachi",
    "pragya", "pratibha", "preeti", "prerna", "priya", "priyanka", "puja",
    "radha", "ranjana", "rashmi", "reena", "rekha", "renuka", "renu", "ritu",
    "ruchi", "rupal", "sadhana", "sakshi", "sangeeta", "sanjana", "sapna",
    "sarita", "savita", "seema", "shanti", "shikha", "shilpa", "shraddha",
    "shreya", "shruti", "shweta", "simran", "sita", "smita", "sneha", "sonia",
    "sudha", "suman", "sunita", "surbhi", "sushmita", "swati", "tanuja",
    "tara", "tripti", "uma", "usha", "vaishali", "vandana", "vani", "varsha",
    "vidya", "vimala", "vineeta", "yamini",
    # Additional common names
    "vaishnavi", "jayashree", "anwesha", "ponnada", "mapui", "saswade",
    # South Indian names
    "arun", "bala", "chandra", "gowri", "hari", "karthik", "lakshman", "mohan",
    "murali", "naga", "padma", "rajan", "ramya", "revathi", "sai", "selva",
    "senthil", "shankar", "sudha", "tamil", "venkat", "venu", "vijaya",
    # Bengali names
    "arnab", "debashish", "dipankar", "indrani", "kaushik", "partha", "prasenjit",
    "prosenjit", "rituparna", "sanjib", "subhash", "sumitra", "supriya", "tapas",
    # Gujarati names
    "bharat", "darshana", "harshad", "jignesh", "kamlesh", "ketan", "nilesh",
    "paresh", "piyush", "rajendra", "shailesh", "tushar", "urvashi",
    # Marathi names
    "ajinkya", "amey", "aniruddha", "ganesh", "milind", "sachin", "sagar",
    "shripad", "tejas", "umesh", "vaibhav", "yashwant",
    # Punjabi names
    "amarjeet", "balwinder", "gurpreet", "harjeet", "jaspreet", "kuldeep",
    "manpreet", "navjot", "parminder", "rajinder", "surinder", "tejinder",
    # International names commonly found in IT
    "david", "michael", "james", "john", "robert", "william", "richard",
    "joseph", "thomas", "christopher", "daniel", "matthew", "anthony", "mark",
    "donald", "steven", "paul", "andrew", "joshua", "kenneth", "kevin", "brian",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan",
    "jessica", "sarah", "karen", "nancy", "lisa", "betty", "margaret", "sandra",
    "ashley", "dorothy", "kimberly", "emily", "donna", "michelle", "carol",
}


# ============================================================================
# International First Names (globally common, conservative set)
# ============================================================================

INTERNATIONAL_FIRST_NAMES: Set[str] = {
    # English / Western
    "adam", "alexander", "alice", "amanda", "andrew", "angela", "anna", "anthony",
    "ashley", "benjamin", "betty", "brian", "carlos", "catherine", "charles",
    "charlotte", "christina", "christopher", "daniel", "david", "deborah", "diana",
    "donald", "dorothy", "edward", "elizabeth", "emily", "emma", "eric", "frank",
    "george", "grace", "hannah", "helen", "henry", "isabella", "jack", "jacob",
    "james", "jason", "jennifer", "jessica", "john", "jonathan", "joseph", "joshua",
    "karen", "katherine", "kevin", "kimberly", "laura", "lauren", "linda", "lisa",
    "margaret", "maria", "mark", "mary", "matthew", "megan", "melissa", "michael",
    "michelle", "nancy", "nathan", "nicholas", "nicole", "olivia", "pamela",
    "patricia", "patrick", "paul", "peter", "philip", "rachel", "raymond",
    "rebecca", "richard", "robert", "ronald", "ruth", "ryan", "samantha", "samuel",
    "sandra", "sarah", "scott", "sharon", "sophia", "stephanie", "stephen",
    "steven", "susan", "thomas", "timothy", "victoria", "virginia", "william",
    # Arabic / Middle Eastern
    "ahmed", "ali", "fatima", "hassan", "hussein", "ibrahim", "khalid", "mohammed",
    "omar", "yusuf", "zainab",
    # East Asian (romanized)
    "chen", "hao", "hui", "lei", "lin", "mei", "ming", "wei", "xin", "yan",
    "yuki", "kenji", "haruki", "sakura",
    # Spanish / Portuguese / Latin American
    "alejandro", "ana", "antonio", "carmen", "diego", "elena", "fernando",
    "francisco", "gabriela", "jose", "juan", "lucia", "luis", "miguel", "pablo",
    "pedro", "rosa", "sofia",
    # French / German / European
    "andreas", "claude", "elena", "eva", "franz", "hans", "jean", "klaus",
    "marie", "pierre", "sophie", "stefan", "wolfgang",
}


# ============================================================================
# Common Indian Last Names / Surnames
# ============================================================================

INDIAN_LAST_NAMES: Set[str] = {
    "agarwal", "aggarwal", "ahuja", "arora", "bajaj", "banerjee", "basu",
    "batra", "bhardwaj", "bhat", "bhatt", "bhattacharya", "bose", "chakraborty",
    "chandra", "chatterjee", "chauhan", "chopra", "das", "desai", "deshmukh",
    "deshpande", "dey", "dhawan", "dixit", "dutta", "gandhi", "ganguly",
    "garg", "ghosh", "gill", "goel", "goyal", "grover", "gupta", "iyer",
    "jain", "jha", "joshi", "kakkar", "kapoor", "kaul", "kaur", "khanna",
    "kohli", "krishnan", "kulkarni", "kumar", "mahajan", "malhotra", "malik",
    "manchanda", "mathur", "mehra", "mehta", "menon", "mishra", "misra",
    "mittal", "mukherjee", "murthy", "nair", "nanda", "narang", "narayan",
    "natarajan", "nayak", "nehru", "oberoi", "padmanabhan", "pai", "pandey",
    "pandit", "parekh", "parikh", "patel", "patil", "prasad", "puri", "rai",
    "rajan", "rajagopal", "rajput", "raman", "ramachandran", "rana", "rao",
    "rastogi", "rathi", "rawat", "reddy", "roy", "saha", "sahni", "saini",
    "sarkar", "saxena", "sen", "sethi", "shah", "sharma", "shastri", "shetty",
    "shukla", "singh", "sinha", "soni", "srivastava", "subramanian", "sundaram",
    "swamy", "tandon", "thakur", "tiwari", "trivedi", "upadhyay", "varma",
    "venkatesh", "verma", "vyas", "yadav",
    # Additional surnames
    "pillai", "naidu", "choudhury", "chowdhury", "biswas", "majumdar", "mitra",
    "acharyya", "acharya", "aiyer", "goswami", "hegde", "kadam", "kale", "karnik",
    "lele", "limaye", "more", "pawar", "sabnis", "sathe", "sovani", "tendulkar",
    # International surnames
    "smith", "johnson", "williams", "brown", "jones", "garcia", "miller",
    "davis", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez", "wilson",
    "anderson", "thomas", "taylor", "moore", "jackson", "martin", "lee", "perez",
    # Additional surnames found in data
    "saswade", "mahapatra", "mapui",
}


# ============================================================================
# Company Names to Redact
# ============================================================================

COMPANY_NAMES: Set[str] = {
    "tcs", "tata consultancy services", "tata", "infosys", "wipro", "hcl",
    "cognizant", "tech mahindra", "accenture", "capgemini", "ibm", "microsoft",
    "google", "amazon", "oracle", "sap", "deloitte", "pwc", "kpmg", "ey",
    "edf energy", "edf", "ultimatix", "nextgenghd",
}


# ============================================================================
# Internal System / Domain Names
# ============================================================================

INTERNAL_SYSTEMS: Set[str] = {
    "ultimatix", "nextgenghd", "global helpdesk", "ghd", "italent",
    "tcscomprod", "sharepoint", "teams", "outlook", "gws",
    # v2.13.0: Security/IT products that should not be redacted as names
    "zscaler", "intune", "avaya", "cisco", "fortinet", "paloalto",
    "crowdstrike", "duo", "okta", "tanium", "qualys", "tenable",
    "splunk", "sccm", "jamf", "airwatch", "vmware", "citrix",
}


# ============================================================================
# Combined Sets for Quick Lookup
# ============================================================================

def get_all_names() -> Set[str]:
    """Get combined set of all first and last names (lowercase)."""
    return INDIAN_FIRST_NAMES | INDIAN_LAST_NAMES


def get_first_names_lower() -> Set[str]:
    """Get first names set (already lowercase)."""
    return {n.lower() for n in INDIAN_FIRST_NAMES}


def get_last_names_lower() -> Set[str]:
    """Get last names set (already lowercase)."""
    return {n.lower() for n in INDIAN_LAST_NAMES}


def get_companies_lower() -> Set[str]:
    """Get company names (already lowercase)."""
    return {c.lower() for c in COMPANY_NAMES}


def get_systems_lower() -> Set[str]:
    """Get internal system names (already lowercase)."""
    return {s.lower() for s in INTERNAL_SYSTEMS}


# ============================================================================
# Export
# ============================================================================

__all__ = [
    'INDIAN_FIRST_NAMES',
    'INDIAN_LAST_NAMES',
    'COMPANY_NAMES',
    'INTERNAL_SYSTEMS',
    'get_all_names',
    'get_first_names_lower',
    'get_last_names_lower',
    'get_companies_lower',
    'get_systems_lower',
]
