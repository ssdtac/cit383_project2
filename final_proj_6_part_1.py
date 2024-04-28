#!/usr/bin/python3


# Final Project Part 1
# Christian Lane, Sachin Ranpal
# lanec6, ranpaldars1


import csv, subprocess, sys, logging, argparse, time, random, string, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def create_groups(file_path):
    # List to store unique group identifiers
    groups = []
    # Open the CSV file
    with open(file_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        # Iterate over each row in the CSV
        for row in reader:
            # Split user groups separated by ';'
            user_groups = row['user_groups'].split(';')
            # Add each unique group to the list
            for group_id in user_groups:
                group_id = group_id.strip()  # Remove leading/trailing spaces

                # if group_id is not null and not already in groups
                if group_id and group_id not in groups:
                    groups.append(group_id)

    # iterate through created list of groups and add them to the system
    for group in groups:
        subprocess.call(['groupadd', group])

# Function to generate unique usernames for each employee
def generate_username(first_name, last_name, existing_usernames):
    username = last_name.lower() + first_name.lower()[0]

    # Check for duplicate usernames
    if username in existing_usernames:
        count = 1
        # If username already exists, append numeric suffix
        while username + str(count) in existing_usernames:
            count += 1
        username += str(count)
    
    return username

# Function to create user accounts for employees
def user_account_creation(data):
    # use a set for an unordered collection of unique elements (usernames)
    existing_usernames = set()

    # Read existing linux usernames from "/etc/passwd"
    with open("/etc/passwd", "r") as passwd_file:
        for line in passwd_file:
            # passwd file is delineated by :
            parts = line.split(":")
            # first part of line is always username
            username = parts[0]
            existing_usernames.add(username)

    # Iterate over employee data, create each user
    for row in data:
        first_name = row['first_name']
        last_name = row['last_name']

        # Generate username for the employee, add it to existing usernames
        username = generate_username(first_name, last_name, existing_usernames)
        existing_usernames.add(username)

        # Generate random password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        try:
            #Create account using subprocess
            subprocess.run(["useradd", "-c", f"{first_name} {last_name}", username, "-m"])
            # Set password for the user
            subprocess.run(f"sudo echo {username}:{password} | chpasswd", shell=True)
            # Log user account creation
            logging.info(f"User account created for {first_name} {last_name} with username: {username} and password: {password}.")
            # Add username and password to employee data
            row['username'] = username
            row['password'] = password
        except subprocess.CalledProcessError as e:
            #log error if account creation fails
            logging.error(f"Error creating user account for {first_name} {last_name}: {e}")


# Function to assign users to appropriate groups 
# takes csv.DictReader object
def group_assignment(data):
    for row in data:
        user = row['username']
        # The groups are separated by ;
        groups = row['user_groups'].split(';')

        # Add user to each group they are in
        for group in groups:
            try:
                # append a group membership to the user
                subprocess.run(["usermod", "-aG", group, user])

                # log the action
                logging.info(f"Added {user} to group {group}.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error adding {user} to group {group}: {e}")

# Function to send email notification with account details
def email_account_creation_status(data, output_file_path):
    try:
        with open(output_file_path, 'w', newline='') as csvfile:
            fieldnames = ['first_name', 'last_name', 'username']
            writer = csv.writer(csvfile)

            # write the top row
            writer.writerow(fieldnames)
            
            # Iterate over employee data
            for row in data:
                # create the formatted line to write to output, omitting sensitive data
                line = [row['first_name'], row['last_name'], row['username']]

                # write to output file
                writer.writerow(line)

                # Send email notification
                # the below line is commented out to prevent excess email spam and to help testing
                send_email(row['email'], row['username'], row['password'], row['first_name'], row['last_name'])
        
        logging.info(f"Account details written to {output_file_path}.")
        return True
    except Exception as e:
        logging.error(f"Error writing account details to {output_file_path}: {e}")
        return False

# Function to send email
# I don't have it send any emails because testing
def send_email(email, username, password, firstname, lastname):
    sender_email = "your_email@example.com"  # Update with your email address
    app_password = ""  # Update with app password at runtime

    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = email
    message['Subject'] = "Your New Account Details"

    body = f"Hello {firstname} {lastname},\n\nYour new account details are as follows:\nUsername: {username}\nPassword: {password}\n\nPlease keep this information secure."
    message.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        # start tls and send hello message
        server.starttls()
        server.ehlo()
        # log in
        server.login(sender_email, app_password)
        # send email
        server.sendmail(sender_email, email, message.as_string())

# function to log actions
def log_actions(logfile_name):
    logging.basicConfig(filename=logfile_name, level=logging.INFO)
    logging.info(f"Program executed at {time.strftime('%Y-%m-%d %H:%M:%S')}.")

# parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description="Employee Account Management Script\nThe script must be run as root.", add_help=True)
    parser.add_argument("E_FILE_PATH", help="Path to the employee file name (including the file name)")
    parser.add_argument("OUTPUT_FILE_PATH", help="Path to the file to store employee account details (including the file name)")
    parser.add_argument("-l", "--log", dest="logfile_name", help="Logfile name", required=True)
    return parser.parse_args()

# Main function
def main():
    # create args object from command line input
    args = parse_arguments()

    # create user groups
    create_groups(args.E_FILE_PATH)

    # set up logger to log actions taken
    log_actions(args.logfile_name)


    # start with new 'data' variable, continuously update it
    with open(args.E_FILE_PATH, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        data = [row for row in reader]


    user_account_creation(data)

    group_assignment(data)

    success = email_account_creation_status(data, args.OUTPUT_FILE_PATH)

    if success:
        print("Employee account creation completed successfully.")
    else:
        print("Error occurred during employee account creation.")


# run the main function
main()
