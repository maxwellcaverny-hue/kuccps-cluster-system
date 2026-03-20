import sys
import os

project_home = os.path.dirname(__file__)
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, ".env"))

from main import app as application