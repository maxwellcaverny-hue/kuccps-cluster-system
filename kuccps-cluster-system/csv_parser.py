import csv

def parse_courses_csv(file_path):

    courses = []

    current_course = None
    current_cluster = None
    current_requirements = None

    with open(file_path, newline='', encoding='utf-8') as file:

        reader = csv.DictReader(file)

        for row in reader:

            # Detect course header row
            if row['COURSE NAME'] and row['COURSE NAME'].strip():

                current_course = row['COURSE NAME'].strip()
                current_cluster = row['CLUSTER'].strip()

                if row['MINIMUM SUBJECT REQUIREMENTS']:
                    current_requirements = row['MINIMUM SUBJECT REQUIREMENTS'].strip()

            # Detect university row
            if row['UNIVERSITY'] and row['UNIVERSITY'].strip():

                courses.append({
                    "course_name": current_course,
                    "cluster": current_cluster,
                    "course_code": row['COURSE CODE'].strip(),
                    "university": row['UNIVERSITY'].strip(),
                    "cutoff": row['CUT-OFF POINT'].strip(),
                    "requirements": current_requirements
                })

    return courses
