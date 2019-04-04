#!/usr/bin/python
##
# CLI script to retrieving data from Azure DevOps
##
import requests
import argparse
import sys
import pandas as pd
from decimal import *
from tabulate import tabulate


class DailyBurnDown:

    url = ''
    groupID = ''
    projectID = ''
    teamID = ''
    token = ''
    currentIterationID = ''
    azure_url = 'dev.azure.com'

    @staticmethod
    def get_arg_parser():
        """ Creates an ArgumentParser to parse the command line options. """

        parser = argparse.ArgumentParser(
            description='Calculate burn down for the Day from Azure DevOps'
        )
        parser.add_argument('-g', '--groupid', help='Group Id from Azure DevOps Board')
        parser.add_argument('-p', '--projectid', help='Project Id from Azure DevOps Board')
        parser.add_argument('-t', '--teamid', help='Team Id from Azure DevOps Board')
        parser.add_argument('-a', '--token', help='Authorization Token to Azure DevOps Board')

        return parser

    def call_api(self):
        """ Call API to fetch details from the given URL """
        # http://docs.python-requests.org/en/latest/user/advanced/#session-objects
        session_with_header = requests.Session()
        session_with_header.headers.update({'Authorization': 'Basic ' + self.token})
        # request and saving the response as object
        response = session_with_header.get(self.url)

        # Check API Response
        if response.status_code == 200:
            return response.json()
        else:
            print("API Failure")
            sys.exit(1)


    def get_current_iteration_id(self):
        """ Get the current iteration id as per Azure DevOps config """

        # Get Current Iteration
        self.url = 'https://' + self.azure_url + '/' + self.groupID \
                   + '/' + self.projectID + '/' + self.teamID \
                   + '/_apis/work/teamsettings/iterations?$timeframe=current&api-version=5.0'
        json_object = self.call_api()

        # Get the First Id from JSON Array
        self.currentIterationID = json_object['value'][0]['id']

    def get_all_current_iteration_workitems_id(self):
        """ Get all workitem id from the current iteration """

        # Get Work Items From Current Iteration
        self.url = 'https://' + self.azure_url + '/' + self.groupID \
                   + '/' + self.projectID + '/' + self.teamID \
                   + '/_apis/work/teamsettings/iterations/' \
                   + self.currentIterationID + '/workitems'
        json_object = self.call_api()

        work_items_id_list = []
        # Loop through the workitem and get the ID's
        for workitem in json_object['workItemRelations']:
            # Append the workitem id's to a list
            work_items_id_list.append(str(workitem['target']['id']))
        # workitems id's to comma separated string - so to fetch all details
        work_items_ids = ",".join(work_items_id_list)
        return work_items_ids

    def get_workitems(self):
        """ Get all cards from the iteration to calculate the burn down """

        work_items_ids = self.get_all_current_iteration_workitems_id()

        # Check to see the team has workitems
        if work_items_ids and not work_items_ids.isspace():
            # fetch all work items with comma separated id's
            self.url = 'https://' + self.azure_url + '/' + self.groupID \
                       + '/' + self.projectID + '/_apis/wit/workitems?ids=' \
                       + work_items_ids
            json_object_work_items = self.call_api()

            over_all_storypoint = 0.0
            board_dict = {}
            # loop through each work item and gather details
            for card in json_object_work_items['value']:
                board_column = 'New'

                # If its a "Task" we consider the story point of the parent
                if card['fields']['System.WorkItemType'] != 'Task':
                    # If 'Reason' is 'Completed' then there is no BoardColumn we need to default to 'Done'
                    if card['fields']['System.Reason'] == 'Completed':
                        board_column = 'Done'
                    else:
                        board_column = card['fields']['System.BoardColumn']

                # check to see if the element is present in the json
                storypoint = 0.0
                if card['fields'].get('Microsoft.VSTS.Scheduling.StoryPoints') is not None:
                    storypoint = Decimal(card['fields']['Microsoft.VSTS.Scheduling.StoryPoints'])
                    over_all_storypoint = Decimal(over_all_storypoint) + storypoint

                if board_column in board_dict:
                    new_value = float(board_dict[board_column].get('point')) + float(storypoint)
                    no_of_card = board_dict[board_column].get('items') + 1
                    board_dict[board_column] = {'point': new_value, 'items': no_of_card}
                else:
                    board_dict[board_column] = {'point': storypoint, 'items': 1}

            # Format the output
            df = pd.DataFrame(board_dict)
            df = df.T
            df.columns = ["items", "points"]
            df = df.astype(int)
            df.loc["TOTAL"] = df.sum().T
            print(tabulate(df, headers="keys", tablefmt="rst"))

        else:
            print("Team, Don't have workitems for the Current Iteration.")

    def run(self):
        """ Main application entry point """
        parser = self.get_arg_parser()
        arguments = parser.parse_args()

        if not all([arguments.projectid, arguments.groupid,
                    arguments.teamid, arguments.token]):
            parser.print_help()
            sys.exit(1)
        else:
            self.groupID = arguments.groupid
            self.projectID = arguments.projectid
            self.teamID = arguments.teamid
            self.token = arguments.token
            # get workitems
            self.get_current_iteration_id()
            self.get_workitems()


if __name__ == '__main__':
    b = DailyBurnDown()
    b.run()
