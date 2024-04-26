#!/usr/bin/python3


# Final project part 2
# Christian Lane, Sachin Darji
# lanec6, 

import os, paramiko, datetime, smtplib, argparse, sys
from email.mime.text import MIMEText
from email.message import EmailMessage
from getpass import getpass

# method for connecting to the remote machine, takes username and password
# returns the ssh client to be used
def connect_to_host(ip_address, username, password):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(ip_address, username=username, password=password)
    return client
    

# finds all affected files in the user's home directory according to lab requirements
def find_affected_files(ssh_client, username):
    affected_files = []

    # datetime objects for comparison
    now = datetime.datetime.now()
    two_weeks_ago = now - datetime.timedelta(weeks=2)
    one_week_ago = now - datetime.timedelta(weeks=1)
    
    # find files created in the last two weeks
    # https://stackoverflow.com/questions/158044/how-to-use-find-to-search-for-files-created-on-a-specific-date
    # this link was very helpful to find how to do this
    # Y/M/D is the date format for all linux
    command = f"find /home/{username} -type f -newermt {two_weeks_ago:%Y%m%d} ! -newermt {one_week_ago:%Y%m%d} -print0 | xargs -0 stat --format '%n %Y'"
    stdin, stdout, stderr = ssh_client.exec_command(command)
    files = stdout.read().decode().splitlines()


    # iterate through each file created in the last two weeks
    for file_info in files:
        # get the right two elements of the split, which are mod time and file path
        file_path, mod_time = file_info.rsplit(' ', 1)

        # change to datetime object for easier conversion later
        mod_time = datetime.datetime.fromtimestamp(int(mod_time))

        # add to affected files list with path and mod time if they are modified between 11pm and 4am
        if 23 <= mod_time.hour or mod_time.hour <= 4:
            # append tuples of file path and mod time
            affected_files.append((file_path, mod_time))

    return affected_files

# function to send email to CTO
def send_email(affected_files, recipient, username):
    # change this only when testing locally
    sender_email = "sender@example.com"
    # not sharing any app password here. We use github for file sharing, so do not put any compromising information in the files
    app_password = "your_app_password"  

    # need the lambda function in order to access the inside of the tuple,
    # to use the file size as the sorting key for min()
    smallest_file = min(affected_files, key=lambda x: os.path.getsize(x[0]))

    # Create the email message
    msg = EmailMessage()
    msg['Subject'] = 'Security Alert: Compromised Files Detected'
    msg['From'] = sender_email
    msg['To'] = recipient

    # body of the email
    body = f"Dear CTO,\n\nThe following files in {username}'s home directory have been identified as potentially compromised:"
    for file_path, mod_time in affected_files:
        # iterate through each compromised file, add to email list
        body += f"\n{file_path} - Last Modified: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}"
    
    body += "\n\nBest regards,\nYour Security Team"
    # attach the message
    msg.attach(MIMEText(body, 'plain'))

    # Attach the smallest file
    with open(smallest_file[0], 'rb') as f:
        msg.add_attachment(f.read(), filename=os.path.basename(smallest_file[0]))

    # connect to mail server
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        # establish connection
        server.starttls()
        server.ehlo()
        # log in
        server.login(sender_email, app_password)

        # send message
        server.sendmail(sender_email, recipient, msg.as_string())


# method for downloading files
def download_files(affected_files, download_path, ssh_client):
    for file_path, _ in affected_files:
        # make local path with the same file basename
        local_path = os.path.join(download_path, os.path.basename(file_path))
        with open(local_path, 'wb') as local_file:
            # open sftp from existing ssh connection to download files
            # read remotely, write locally
            with ssh_client.open_sftp().file(file_path, 'rb') as remote_file:
                local_file.write(remote_file.read())


# main method
def main():

    # add arguments
    parser = argparse.ArgumentParser(description='Monitor and report files suspected of being compromised on remote systems.')
    parser.add_argument('ip_address', help='IP address of the remote computer')
    parser.add_argument('username', help='Username on the remote computer')
    parser.add_argument('-d', '--disp', action='store_true', help='Display contents of the affected files')
    parser.add_argument('-e', '--email', required=True, help='Email address to send the report to')
    parser.add_argument('-p', '--path', help='Path to download affected files, defaults to home directory if not specified')

    # parse arguments
    args = parser.parse_args()

    # prompt for password
    password = getpass('Enter your password: ')

    # connect to the remote machine
    ssh_client = connect_to_host(args.ip_address, args.username, password)

    # find affected files
    affected_files = find_affected_files(ssh_client, args.username)

    # if there are no compromised files, end the program, don't send an email
    if not affected_files:
        print("No affected files found.")
        ssh_client.close()
        sys.exit(0)

    # display affected files if "-d" is used
    if args.disp:
        for file_path, mod_time in affected_files:
            print(f'{file_path} - Last Modified: {mod_time.strftime("%Y-%m-%d %H:%M:%S")}')

    # Send email to CTO
    send_email(affected_files, args.email, args.username)

    # download files
    # set to provided arg path (if provided) otherwise home dir
    download_path = args.path if args.path else os.path.expanduser("~")
    download_files(affected_files, download_path, ssh_client)

    ssh_client.close()
    print("Operation completed successfully.")

# run the program
main()