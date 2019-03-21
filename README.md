# Gogle Drive explorer
[![paypal](https://www.paypalobjects.com/en_US/i/btn/btn_donateCC_LG.gif)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=DH7984HPJ8C4N&currency_code=EUR&source=url)

## What is Google Drive explorer?
drive-explorer is a CLI utility to explore the content of your Google Drive folders in a fast and efficient way

## Features
drive-explorer is able to:
* traverse complex drive folder trees using python multiprocessing module
* explore as many folder you want in parallel
* write the result of the exploration to different output formats (csv, tsv, json, gsheet, sqlite) so that you can analyze it with your tool of choice
* manage different credentials to explore folders belonging to different accounts

## Requirements
To be able to use this script you need:
* a Google developer project with the following APIs enabled
  * [Google Drive API](https://developers.google.com/drive/): these APIs are used, based on the parameters, to read folders contents and metadata.
  * [Google Sheets API](https://developers.google.com/sheets/): If the user require a Google Sheet output these APIs are used to create it.

## Important
This script has only been tested with python 3.6 so I strongly recommend to use that version of the python interpreter or a following one.
  
## First time use
If you are not familiar with the [Google API console](https://console.developers.google.com/) I recommend you to read some documentation before attempting this.

Here are the main steps:
* Create a new project ([here](https://cloud.google.com/resource-manager/docs/creating-managing-projects?visit_id=636812630402595025-4052861048&rd=1) for more details):
  * Go to the [Manage resources page](https://console.cloud.google.com/cloud-resource-manager) in the GCP Console
  * Create a new project. Be sure to note down the name you give to your project 
* Enable the required APIs
  * Open the [Library page](https://console.developers.google.com/apis/library) in the API Console
  * Make sure that in the top left dropdown the selected project is the one you just created. If it is not, switch to it.
  * Search and Enable the following APIs
    * Google Drive API
    * Google Sheets API
* Create Credentials
  * Open the [Credentials page](https://console.developers.google.com/apis/credentials)
  * Make sure that in the top left dropdown the selected project is the one you just created. If it is not, switch to it.
  * From the center "Create credentials" drop menu choose _OAuth client ID_
  * If prompted to do so Configuare your consent screen
    * Click the _Configuare consent screen_ button
    * Fill the _Application name_ field
    * click the save button at the bottom of the page (yes, you can leave the rest of the info blank)
  * choose _Other_ as Application type
  * Type your desired name for the credentials (note it down, as you will use it) and click the create button. Read the upcoming pop-up and dismiss it with the OK button
  * You now need to download the JSON file for the credentials you've just created.
  To do so, next to the credentials you just created click the Download JSON button (the arrow pointing down) and save the newly created file in your directory of choice.
  Be sure to take note of where you save this file, you will need it to run the tool: this is the client secret file required by the tool (refer to the -cf parameters in the documentation below).  

## Commands
Using drive explorer you can
* interact with folders
  * using the _folder explore_ command allows you to recursively explore a list folders and their contents
  * the _folder list_ allows you to list all the files inside a drive folder
* manage credentials used to explore drive
  * using the _credential add_ command you can add new credentials to use while exploring Google Drive
  * using the _credential delete_ command you can delete a credential
  * using the _credential list_ command you can have an overview of the existing credentials
  * using the _credential default_ you can make an existing credential the default one 

##### folder explore command
The _folder explore_ is probably the command that you will use most as is the one used to recursively explore folders.

This command tries to be smart about credentials: if no credential is present, the authorization flow will start otherwise 
the default credentials are used. Use option -u to specify the desired user.

Unless differently specified, this command will start from the "_root_" folder that correspond to the _My Drive_ folder
in the UI. Use the -id option to specify a different folder ID.

Use -o option to specify the output format of the results.

    usage: drive-exploter folder explore [-h] [-id [FOLDER_ID [FOLDER_ID ...]]] [-it]
                          [-fm FILE_MATCH] [-cs] [-tm TYPE_MATCH]
                          [-fs FOLDER_SEPARATOR] [-nw NUM_WORKERS] [-u USER]
                          [-o OUTPUT] [-cf CREDENTIAL_FILE]
                          [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
    
    optional arguments:
      -h, --help            show this help message and exit
      -id [FOLDER_ID [FOLDER_ID ...]], --folder-id [FOLDER_ID [FOLDER_ID ...]]
                            The id of the folder(s) you want to explore. "My
                            Drive" by default (default: ['root'])
      -it, --include-trashed
                            Do we want to include trashed files? (default: False)
      -fm FILE_MATCH, --file-match FILE_MATCH
                            Python regex to filter the file names. Does not work
                            on folders. (default: .*)
      -cs, --case-sensitive
                            Is the python file match regex case sensitive?
                            (default: False)
      -tm TYPE_MATCH, --type-match TYPE_MATCH
                            Python regex to filter the file types. Does not work
                            on folders. (default: .*)
      -fs FOLDER_SEPARATOR, --folder-separator FOLDER_SEPARATOR
                            folder separator for output file (default: \)
      -nw NUM_WORKERS, --num-workers NUM_WORKERS
                            number of parallel processes (default: 24)
      -u USER, --user USER  email address to be used (default: )
      -o OUTPUT, --output OUTPUT
                            Path to the output file. Supported formats: .csv, .gs,
                            .gsheet, .json, .sqlite, .sqlite3, .tsv (default:
                            None)
      -cf CREDENTIAL_FILE, --credential-file CREDENTIAL_FILE
                            Path to the JSON file containing the configuration in
                            the Google client secrets format (default:
                            client_id.json)
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Set the logging level (default: INFO)
                            
#### folder list command
This command is similar to the _folder explore_ one, the difference is that this command won't recurse over the specified
folder contents

Use -o option to specify the output format of the results.


    usage: drive-explorer folder list [-h] [-id [FOLDER_ID [FOLDER_ID ...]]] [-it]
                                      [-fm FILE_MATCH] [-cs] [-tm TYPE_MATCH]
                                      [-fs FOLDER_SEPARATOR] [-u USER] [-o OUTPUT]
                                      [-cf CREDENTIAL_FILE]
                                      [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
    
    optional arguments:
      -h, --help            show this help message and exit
      -id [FOLDER_ID [FOLDER_ID ...]], --folder-id [FOLDER_ID [FOLDER_ID ...]]
                            The id of the folder(s) you want to explore. "My
                            Drive" by default (default: ['root'])
      -it, --include-trashed
                            Do we want to include trashed files? (default: False)
      -fm FILE_MATCH, --file-match FILE_MATCH
                            Python regex to filter the file names. Does not work
                            on folders. (default: .*)
      -cs, --case-sensitive
                            Is the python file match regex case sensitive?
                            (default: False)
      -tm TYPE_MATCH, --type-match TYPE_MATCH
                            Python regex to filter the file types. Does not work
                            on folders. (default: .*)
      -fs FOLDER_SEPARATOR, --folder-separator FOLDER_SEPARATOR
                            folder separator for output file (default: \)
      -u USER, --user USER  email address to be used (default: )
      -o OUTPUT, --output OUTPUT
                            Path to the output file. Supported formats: .csv, .gs,
                            .gsheet, .json, .sqlite, .sqlite3, .tsv (default:
                            None)
      -cf CREDENTIAL_FILE, --credential-file CREDENTIAL_FILE
                            Path to the JSON file containing the configuration in
                            the Google client secrets format (default:
                            client_id.json)
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Set the logging level (default: INFO)

#### credentail add command
This command will allow you to add more credentials to the tool. All the credentials are saved in the drive_explore.sqlite3
file. You don't need to add credentials at the first use as the explorer command will add them automatically for you if 
not present or use the default one if not specified. You need this command everytime you want to manage more than one
credential. 

    usage: drive-explorer credential add [-h] [-md] [-cf CREDENTIAL_FILE]
                                         [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
    
    optional arguments:
      -h, --help            show this help message and exit
      -md, --make-default   Is this going to be the default credential? (default:
                            False)
      -cf CREDENTIAL_FILE, --credential-file CREDENTIAL_FILE
                            Path to the JSON file containing the configuration in
                            the Google client secrets format (default:
                            client_id.json)
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Set the logging level (default: INFO)

#### credentail delete command
Use this command if you want to get rid of one of the stored credentials in the database.

    usage: drive-explorer credential delete [-h] -u USER
                                            [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
    
    optional arguments:
      -h, --help            show this help message and exit
      -u USER, --user USER  email address to be used (default: None)
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Set the logging level (default: INFO)

#### credentail list command
Use this command to list all the credentials in the database

    usage: drive-explorer credential list [-h]
                                          [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
    
    optional arguments:
      -h, --help            show this help message and exit
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Set the logging level (default: INFO)

#### credentail default command
Use this command if you have more than one credential in the database and you want to make one of them the default one.

    usage: drive-explorer credential default [-h] -u USER
                                             [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]
    
    optional arguments:
      -h, --help            show this help message and exit
      -u USER, --user USER  email address to be used (default: None)
      -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Set the logging level (default: INFO)

Here are some command examples

    drive-explorer folder explore -o test.csv
This is the basic command to recursively explore your "My Drive" folder and write the output to test.csv

    drive-explorer folder explore -id 0B_PHB7sHcRJMRlktOU1kNXFHMnM -o test2.csv 
This is the basic comand to explore a specific folder with id 0B_PHB7sHcRJMRlktOU1kNXFHMnM
    
   
## Author
I am Lorenzo Persichetti and I am passionate about cloud technologies.
I personally developed this tool to face to fit my need of sorting out what is inside my Google Drive.

I have used this tool many times and it proved to be a useful companion .

This is also my first contribution to the open source community, so any feedback is absolutely welcome.
