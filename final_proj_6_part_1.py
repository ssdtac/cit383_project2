#!/usr/bin/python
import csv, subprocess, os, sys, logging, argparse, time, random, string, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Function to create user groups based on unique identifiers in the employee file
def group_creation(file_path):
    # List to store unique group identifiers
    groups = []

    try:
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
                    if group_id and group_id not in groups:
                        groups.append(group_id)
    
    except FileNotFoundError:
        # Log error if file not found
        logging.error("File not found. Please provide a valid file path.")
        return None
    
    return groups

# Function to generate usernames for each employee
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
    existing_usernames = set()
    # Read existing usernames from "/etc/passwd"
    with open("/etc/passwd", "r") as passwd_file:
        for line in passwd_file:
            parts = line.split(":")
            username = parts[0]
            existing_usernames.add(username)

    # Iterate over employee data
    for row in data:
        first_name = row['first_name']
        last_name = row['last_name']
        # Generate username for the employee
        username = generate_username(first_name, last_name, existing_usernames)
        # Generate random password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        try:
            # Create user account using subprocess
            subprocess.run(["useradd", "-c", f"{first_name} {last_name}", username, "-m"])
            # Set password for the user
            subprocess.run(["passwd", "--stdin", username], input=password.encode(), check=True)
            # Log user account creation
            logging.info(f"User account created for {first_name} {last_name} with username: {username} and password: {password}.")
            # Add username and password to employee data
            row['username'] = username
            row['password'] = password
        except subprocess.CalledProcessError as e:
            # Log error if user account creation fails
            logging.error(f"Error creating user account for {first_name} {last_name}: {e}")
    return data

# Function to assign users to appropriate groups
def group_assignment(data):
    for row in data:
        user = row['username']
        groups = row['user_groups'].split(';')
        # Add user to each group
        for group in groups:
            try:
                subprocess.run(["usermod", "-aG", group, user])
                logging.info(f"Added {user} to group {group}.")
            except subprocess.CalledProcessError as e:
                logging.error(f"Error adding {user} to group {group}: {e}")
    return data

# Function to send email notification with account details
def email_account_creation_status(data, output_file_path):
    try:
        with open(output_file_path, 'w', newline='') as csvfile:
            fieldnames = ['first_name', 'last_name', 'username', 'email']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            writer.writeheader()
            # Iterate over employee data
            for row in data:
                writer.writerow(row)
                # Send email notification
                send_email(row['email'], row['username'], row['password'])
        
        logging.info(f"Account details written to {output_file_path}.")
        return True
    except Exception as e:
        logging.error(f"Error writing account details to {output_file_path}: {e}")
        return False

# Function to send email
def send_email(email, username, password):
    sender_email = "your_email@example.com"  # Update with your email address
    sender_password = "your_password"  # Update with your email password

    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = email
    message['Subject'] = "Your New Account Details"

    body = f"Hello,\n\nYour new account details are as follows:\nUsername: {username}\nPassword: {password}\n\nPlease keep this information secure."
    message.attach(MIMEText(body, 'plain'))

    with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, email, message.as_string())

# Function to log actions
def log_actions(logfile_name):
    logging.basicConfig(filename=logfile_name, level=logging.INFO)
    logging.info(f"Program executed at {time.strftime('%Y-%m-%d %H:%M:%S')}.")

# Function to parse command-line arguments
def parse_arguments():
    parser = argparse.ArgumentParser(description="Employee Account Management Script")
    parser.add_argument("E_FILE_PATH", help="Path to the employee file name (including the file name)")
    parser.add_argument("OUTPUT_FILE_PATH", help="Path to the file to store employee account details (including the file name)")
    parser.add_argument("-l", "--log", dest="logfile_name", help="Logfile name", required=True)
    parser.add_argument("-v", "--version", action="version", version="%(prog)s 1.0")
    return parser.parse_args()

# Main function
def main():
    args = parse_arguments()
    log_actions(args.logfile_name)
    groups = group_creation(args.E_FILE_PATH)

    if not groups:
        sys.exit(1)
    
    with open(args.E_FILE_PATH, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        data = [row for row in reader]

    data = user_account_creation(data)
    data = group_assignment(data)
    success = email_account_creation_status(data, args.OUTPUT_FILE_PATH)

    if success:
        print("Employee account creation completed successfully.")
    else:
        print("Error occurred during employee account creation.")

# Execute main function if script is run directly
if __name__ == "__main__":
    main()
