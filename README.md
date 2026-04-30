# MCAE Email Template Updater

This project helps a marketing operations user do two things with Marketing Cloud Account Engagement (Pardot) email templates:

1. Extract email templates from MCAE into a local working folder.
2. Update those templates back into MCAE after editing the files.

The script is designed to be run from a terminal, but the workflow is intentionally simple:

1. Complete setup (including Salesforce External Client Application details).
2. Run a connection check.
3. Run an extract.
4. Edit the exported HTML and text files.
5. Mark the rows you want to update in the spreadsheet.
6. Run the import.

If you have not installed Python or set up the project yet, jump to [Setup](#setup).

## Running the Script

All commands below assume you are already inside the project folder in a terminal.

If you want to see the available commands or options at any time, use:

```powershell
python main.py --help
python main.py extract --help
python main.py import --help
```

On the first run, the script will create a `.env` file from `.env-sample`, prompt you for your Salesforce and MCAE values, save them, and stop. That is expected. Run the same command a second time after the prompts are complete.

### Testing Authentication and Setup

Use the `test-auth` command to confirm that the script has the configuration it needs and can successfully connect to Salesforce and MCAE.

Before running this command, complete [Setting Up a Salesforce External Client Application](#setting-up-a-salesforce-external-client-application).

Example command:

```powershell
python main.py test-auth
```

What this command checks:

1. Required configuration values are present in `.env`.
2. Salesforce OAuth works with your External Client Application.
3. The Pardot Business Unit ID is accepted.
4. The script can make a simple Pardot API request.

This is the best first command to run after setup.

### Working with the Extract Script

Use the extract command to download email templates into a timestamped working folder. The folder will include:

1. An `email_templates.csv` spreadsheet.
2. One folder per campaign and email.
3. Paired `content-original` and `content-updated` files for HTML and text.

Example commands:

```powershell
python main.py extract
python main.py extract --name "Webinar"
python main.py extract --campaign "Annual Customer Conference"
python main.py extract --tags "invitations"
```

What to expect:

1. The script finds matching email templates.
2. It asks you to confirm before downloading.
3. It asks where to save the export folder.
4. It creates a working directory such as `extract_20260413_202850`.
5. It writes both original and editable copies of each template.

After the extract finishes, update the files named `content-updated.html` and `content-updated.txt`. Leave the `content-original` files alone so you always have a reference copy.

### Working with the Import Script

Use the import command after you have finished editing the exported files.

Before importing:

1. Open `email_templates.csv` in Excel or another spreadsheet tool.
2. In the `ready_to_update` column, set the rows you want to upload to `Yes`.
3. Make sure the file paths in `html_file_path` and `text_file_path` still point to the edited files.

Example command:

```powershell
python main.py import --dir extract_20260413_202850
```

What the import does:

1. Reads `email_templates.csv` from the folder you pass with `--dir`.
2. Checks that each referenced updated file exists.
3. Downloads a fresh backup of the current MCAE content before changing anything.
4. Uploads the updated HTML and text content for rows marked `Yes`.
5. Writes the result back into the `update_status` column in the spreadsheet.

If an update fails, the script stops immediately after recording the error in the CSV.

## Setup

Recommended order:

1. [Install Python](#installing-python-on-mac-and-windows).
2. [Set up your Salesforce External Client Application](#setting-up-a-salesforce-external-client-application) so you have the client ID and secret.
3. [Download or clone this repository](#getting-the-files-from-github).
4. [Set up the project dependencies](#setting-up-the-project).
5. [Run test-auth](#testing-authentication-and-setup) to create/check `.env` and verify connectivity.

## Setting Up a Salesforce External Client Application

This script authenticates to Salesforce using an External Client Application with the Client Credentials flow.

Use this guide for the Salesforce-side setup:

<https://www.cyfunolabs.com/2025/11/18/calling-the-account-engagement-api-from-salesforce/>

For this project, you only need to complete steps one and two from that guide.

You will need these values when the script prompts you on first run:

1. `SF_URL`: Your Salesforce My Domain URL, such as `https://yourorg.my.salesforce.com`
2. `CLIENT_ID`: The External Client Application consumer key
3. `CLIENT_SECRET`: The External Client Application consumer secret
4. `PARDOT_BUSINESS_UNIT_ID`: Your MCAE business unit ID
5. `PARDOT_ORG_TYPE`: Usually `production`, but use `sandbox` or `demo` if that matches your environment

The first time you run the script, it will ask for those values and store them in a local `.env` file.

## Installing Python on Mac and Windows

This project requires Python 3. If you do not already have it installed, use one of these approaches.

### Windows

1. Go to the Python downloads page: <https://www.python.org/downloads/windows/>
2. Install a current Python 3 release.
3. During installation, make sure `Add Python to PATH` is selected.
4. After installation, open PowerShell and run:

```powershell
python --version
```

If that does not work, try:

```powershell
py --version
```

### Mac

1. Go to the Python downloads page: <https://www.python.org/downloads/macos/>
2. Install a current Python 3 release.
3. Open Terminal and run:

```bash
python3 --version
```

If your Mac already has Python, make sure the command returns Python 3, not Python 2.

## Getting the Files from GitHub

Use whichever option is easier for you.

### Option 1: Download ZIP from GitHub

1. Open the repository in GitHub.
2. Select `Code`.
3. Select `Download ZIP`.
4. Extract the ZIP file to a folder on your computer.

### Option 2: Clone with Git

If you already use Git, clone the repository from a terminal:

```powershell
cd Documents
git clone https://github.com/Cyfuno-Labs/mcae-email-template-export-import.git
cd mcae-email-template-export-import
```

Mac/Linux equivalent:

```bash
cd ~/Documents
git clone https://github.com/Cyfuno-Labs/mcae-email-template-export-import.git
cd mcae-email-template-export-import
```

After cloning, if there are changes made in the future, you can update your code by running (from within the project directory):
```bash
git pull
```

## Setting Up the Project

Open a terminal in the project folder you downloaded from GitHub.

### Windows

Create a virtual environment and install the required packages:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If your machine uses the `py` launcher instead of `python`, you can use this version instead:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install --upgrade pip
pip install -r requirements.txt
```

### Mac

Create a virtual environment and install the required packages:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install -r requirements.txt
```

After setup, you can go back to the commands in [Running the Script](#running-the-script).

As a quick verification step, run:

```powershell
python main.py test-auth
```

If that succeeds, you are ready to use the extract and import commands.

## Getting Help

If you need help with setup, Salesforce configuration, or troubleshooting the extract/import process, contact Cyfuno Labs for additional information and support.