import os
import json
import re
from typing import Dict, Text, Any, List
import logging
from dateutil import parser
import sqlalchemy as sa
import sqlite3
from numpy import random
import actions.mysql as mysql

import twilio
from twilio.rest import Client

import pymongo

import spacy
import en_core_web_sm
import nltk
from nltk.corpus import wordnet
from bltk.langtools import PosTagger
from bltk.langtools import Tokenizer

import bangla
from banglanum2words import num_convert
from num2words import num2words

import datetime
from rasa_sdk.events import ReminderScheduled

#Global variable is here
#-----------------------------------------------------
nlp = en_core_web_sm.load()
nlu = spacy.load("en_core_web_sm")

GlobalList = []
flag = False
#-----------------------------------------------------

from rasa_sdk.events import SlotSet, AllSlotsReset, Restarted, UserUtteranceReverted, FollowupAction, ActionReverted, UserUttered, Form

from rasa_sdk.interfaces import Action
from rasa_sdk.events import (
    SlotSet,
    EventType,
    ActionExecuted,
    SessionStarted,
    Restarted,
    FollowupAction,
    UserUtteranceReverted,
    AllSlotsReset,
)
from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher

from actions.parsing import (
    parse_duckling_time_as_interval,
    parse_duckling_time,
    get_entity_details,
    parse_duckling_currency,
)

from actions.profile_db import create_database, ProfileDB

from actions.custom_forms import CustomFormValidationAction
from rasa_sdk.types import DomainDict
from actions.converter import is_ascii, BnToEn_Word, BnToEn

db_manager = mysql.DBManager()
logger = logging.getLogger(__name__)

# The profile database is created/connected to when the action server starts
# It is populated the first time `ActionSessionStart.run()` is called.

PROFILE_DB_NAME = os.environ.get("PROFILE_DB_NAME", "profile")
PROFILE_DB_URL = os.environ.get("PROFILE_DB_URL", f"sqlite:///{PROFILE_DB_NAME}.db")
ENGINE = sa.create_engine(PROFILE_DB_URL)
create_database(ENGINE, PROFILE_DB_NAME)

profile_db = ProfileDB(ENGINE)


class ActionSessionStart(Action):
    """Executes at start of session"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_session_start"

    @staticmethod
    def _slot_set_events_from_tracker(
        tracker: "Tracker",
    ) -> List["SlotSet"]:
        """Fetches SlotSet events from tracker and carries over keys and values"""

        # when restarting most slots should be reset
        relevant_slots = ["currency"]

        return [
            SlotSet(
                key=event.get("name"),
                value=event.get("value"),
            )
            for event in tracker.events
            if event.get("event") == "slot" and event.get("name") in relevant_slots
        ]

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:
        """Executes the custom action"""
        # the session should begin with a `session_started` event
        events = [SessionStarted()]

        events.extend(self._slot_set_events_from_tracker(tracker))

        # create a mock profile by populating database with values specific to tracker.sender_id
        profile_db.populate_profile_db(tracker.sender_id)
        currency = profile_db.get_currency(tracker.sender_id)

        #-----------------------------------------Session Id Exists or Not-------------------------------
        
        sv=tracker.current_slot_values()
        sv_json_object = json.dumps(sv, indent = 4)
        phone = tracker.get_slot("phone_number")
        print("session started and set everything Null to DB initially")
        account = db_manager.set_session_id(
                tracker.sender_id, phone, sv_json_object
            )
        print(account)
        
        #---------------------------------------------------------------------------------------------------------------

        # initialize slots from mock profile
        events.append(SlotSet("currency", currency))

        # add `action_listen` at the end
        events.append(ActionExecuted("action_listen"))

        return events


class ActionRestart(Action):
    """Executes after restart of a session"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_restart"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:
        """Executes the custom action"""
        return [Restarted(), FollowupAction("action_session_start")]

class ActionResetSlots(Action):
    """action_reset_all_slots"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_all_slots"
    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print ("slots are being reset")
        return [AllSlotsReset()]

# class ResetcardBillForm(Action):
#     """action_reset_card_bill_form"""

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "action_reset_card_bill_form"

#     async def run(
#         self,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         print(tracker.latest_message['intent'].get('name'))
#         """Executes the action"""
#         print("Reset Slot Function Called.")
#         return[ SlotSet("card_number", None),
#                 SlotSet("Valid_DATE", None),
#                 SlotSet("CCV", None),
#                 SlotSet("amount-of-money", None),
#                 ]

# class ActionCardBill(FormValidationAction):
#     """validate_card_bill_form"""
#     prev_ccv=''
#     count = 0

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "validate_card_bill_form"

#     async def validate_card_number(
#         self,
#         slot_value: Any,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         """Executes the action"""
#         print("validate_card_number")
        
#         card = tracker.get_slot("card_number")
#         print("card Number is : ", card)
        
#         #BANGLA Check Here
#         if (not is_ascii(card)):  #If Bangla then enter here. is_ascii(otp) True for English
#             cn = None
#             if card.isnumeric():
#                 cn = BnToEn(card)
#                 print(str(cn))
#                 card = str(cn)
#                 print("card Number is ", card)
#                 tracker.slots["card_number"] = card
#                 if len(card)!=16 or card == None:
#                     dispatcher.utter_message(response="utter_invalidCARDnumber")
#                     return {"card_number": None}
#                 else:
#                     print("Correct card Number")
#                     account = db_manager.set_slot_value(tracker.sender_id, "card_number", card)
#                     return {"card_number": card}
#         else:
#             if len(card)!=16 or card == None:
#                 dispatcher.utter_message(response="utter_invalidCARDnumber")
#                 return {"card_number": None}
#             else:
#                 print("Correct card Number")
#                 account = db_manager.set_slot_value(tracker.sender_id, "card_number", card)
#                 return {"card_number": card}
#                 # #-----------------------------------------------------------------
#                 # dispatcher.utter_message(response = "utter_CardNumber_confirm")
                        
#                 # if self.count == 0:
#                 #     print("Inside flag")
#                 #     return [FollowupAction("utter_CardNumber_confirm")]

#                 # if tracker.latest_message['intent'].get('name') == "affirm":
#                 #     self.count == 1
#                 #     print(tracker.latest_message['intent'].get('name'))
#                 #     print(type(tracker.latest_message['intent'].get('name')))
#                 #     account = db_manager.set_slot_value(tracker.sender_id, "card_number", card)
#                 #     return {"card_number": card}
#                 # if tracker.latest_message['intent'].get('name') == "deny":
#                 #     tracker.slots["card_number"] = None
#                 #     print(tracker.latest_message['intent'].get('name'))
#                 #     print(type(tracker.latest_message['intent'].get('name')))
#                 #     return[]
#                 # #-----------------------------------------------------------------
                
    
#     async def validate_Valid_DATE(
#         self,
#         slot_value: Any,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         """Executes the action"""
#         print("validate_Expiry_DATE")
#         card_date = tracker.get_slot("Valid_DATE")
#         print("card expiry date is : ", card_date)
#         currentyear = datetime.datetime.now().year
#         currentmonth = datetime.datetime.now().month
#         print(currentmonth)
#         print(f"this is {currentyear}, and we are not getting smart.")
#         currentyear = str(currentyear)
#         currentyear = currentyear[-2:]
#         currentyear = int(currentyear)
#         print(currentyear)
#         #BANGLA Check Here
#         # if (not is_ascii(card_date)):  #If Bangla then enter here. is_ascii(otp) True for English
#         #     cn = None
#         #     if card.isnumeric():
#         #         cn = BnToEn(card)
#         #         print(str(cn))
#         #         card = str(cn)
#         #         print("card Number is ", card)
#         #         tracker.slots["card_number"] = card
#         #     return {"card_number": card}
        
#         if len(card_date)!=5 or card_date == None:
#             dispatcher.utter_message(response="utter_invalidValid_DATE")
#             return {"Valid_DATE": None}
#         else:
#             expiry_date = str(card_date)
#             print("first 2 digits: ", expiry_date[0:2])
#             month = int(expiry_date[0:2])
#             print("last 2 digit: ", expiry_date[-2:])
#             year = int(expiry_date[-2:])
            
#             if currentyear == year:
#                 if month >= currentmonth:
#                     print("Expiry date is correct.")
#                     account = db_manager.set_slot_value(tracker.sender_id, "Valid_DATE", card_date)
#                     return {"Valid_DATE": card_date}
#                 else:
#                     dispatcher.utter_message(response="utter_invalidValid_DATE")
#                     return {"Valid_DATE": None}
#             elif year > currentyear:
#                 if month> 0 and month<=12:
#                     print("Expiry date is correct.")
#                     account = db_manager.set_slot_value(tracker.sender_id, "Valid_DATE", card_date)
#                     return {"Valid_DATE": card_date}
#                 else:
#                     dispatcher.utter_message(response="utter_invalidValid_DATE")
#                     return {"Valid_DATE": None}
#             else:
#                 dispatcher.utter_message(response="utter_invalidValid_DATE")
#                 return {"Valid_DATE": None}


#     async def validate_CCV(
#         self,
#         slot_value: Any,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         """Executes the action"""
#         amount_money=''
#         print("validate_CCV")
#         ccv = tracker.get_slot("CCV")
#         print("card ccv is : ", ccv)
#         if(len(self.prev_ccv)==3):
#             amount_money=ccv
#             ccv=self.prev_ccv
#             self.prev_ccv=''
#             return {"CCV": ccv,"amount-of-money": amount_money}
#         else:
#             #BANGLA Check Here
#             if (not is_ascii(ccv)):  #If Bangla then enter here. is_ascii(otp) True for English
#                 cn = None
#                 if ccv.isnumeric():
#                     cn = BnToEn(ccv)
#                     print(str(cn))
#                     ccv = str(cn)
#                     print("CCV Number is ", ccv)
#                     tracker.slots["CCV"] = ccv
#                     if len(ccv)!=3 or ccv == None:
#                         dispatcher.utter_message(response="utter_invalidCCV")
#                         return {"CCV": None}
#                     else:
#                         print("Correct CCV Number")
#                         self.prev_ccv = ccv
#                         account = db_manager.set_slot_value(tracker.sender_id, "CCV", ccv)
#                         return {"CCV": ccv}
#             else:
#                 if len(ccv)!=3 or ccv == None:
#                     dispatcher.utter_message(response="utter_invalidCCV")
#                     return {"CCV": None}
#                 else:
#                     print("Correct CCV Number")
#                     self.prev_ccv = ccv
#                     account = db_manager.set_slot_value(tracker.sender_id, "CCV", ccv)
#                     return {"CCV": ccv}


#     async def validate_amount_of_money(
#         self,
#         slot_value: Any,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         print("CCV in amount validation:", tracker.get_slot("CCV"))
#         amount = tracker.get_slot("amount-of-money")
#         print("amount inside function: ", amount)

#         account_balance = profile_db.get_account_balance(tracker.sender_id)

#         number = None
#         #BANGLA Check Here
#         if(not is_ascii(amount)):  #If Bangla then enter here
#             print("Hello, Check Bangla")
#             if amount.isnumeric():
#                 number = BnToEn(amount)
#                 amount = str(number)
#                 print("Number : ", number)
#                 print(amount)
#                 if(int(amount)<=0):
#                     dispatcher.utter_message(response="utter_invalidAMOUNT")
#                     # print("1")
#                     return {"amount-of-money": None}
#                 else:
#                     # print("2")
#                     account = db_manager.set_slot_value(tracker.sender_id, 'amount-of-money', amount)
#                     return {"amount-of-money": amount}
#             else:
#                 # print("3")
#                 return[ SlotSet("amount-of-money", None),
#                         ]
#         else:
#             # print("4")
#             if(int(amount)<=0):
#                 # print("5")
#                 dispatcher.utter_message(response="utter_invalidAMOUNT")
#                 return {"amount-of-money": None}
#             else:
#                 account = db_manager.set_slot_value(tracker.sender_id, 'amount-of-money', amount)
#                 print("Amount is ", amount)
#                 return {"amount-of-money": amount}

#         return []

# class ResetCCV(Action):
#     """action_reset_CCV"""

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "action_reset_CCV"

#     async def run(
#         self,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         print(tracker.latest_message['intent'].get('name'))
#         """Executes the action"""
#         print("Reset Slot Function Called.")
#         return[
#                 SlotSet("CCV", None),
#             ]
class ResetCardNumber(Action):
    """action_reset_card_number"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_card_number"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        """Executes the action"""
        print("Reset Slot Function Called.")
        return[
                SlotSet("card_number", None),
            ]
# class ResetValidDATE(Action):
#     """action_reset_Valid_DATE"""

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "action_reset_Valid_DATE"

#     async def run(
#         self,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         print(tracker.latest_message['intent'].get('name'))
#         """Executes the action"""
#         print("Reset Slot Function Called.")
#         return[
#                 SlotSet("Valid_DATE", None),
#             ]
class ResetAmount(Action):
    """action_reset_AMOUNT"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_AMOUNT"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        """Executes the action"""
        print("Reset Slot Function Called.")
        return[
                SlotSet("amount-of-money", None),
            ]
class AffirmOrDeny(Action):
    """action_check_response"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_check_response"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("response check Function Called.")

        if tracker.latest_message['intent'].get('name') == "affirm":
            print("Got, Yes")
            print(tracker.latest_message['intent'].get('name'))
        if tracker.latest_message['intent'].get('name') == "deny":
            tracker.slots["card_number"] = None
            print(tracker.slots["card_number"])
            print(tracker.latest_message['intent'].get('name'))
            # return [FollowupAction('card_bill_form_c_number')]
            return [SlotSet("card_number", None), Form("card_bill_form_c_number")]

class ActionCardnumberCard(FormValidationAction):
    """validate_card_bill_form_c_number"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "validate_card_bill_form_c_number"

    async def validate_card_number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        
        
        print("validate_card_number")
        card = tracker.get_slot("card_number")
        print("card Number is : ", card)
        
        
        #BANGLA Check Here
        if (not is_ascii(card)):  #If Bangla then enter here. is_ascii(otp) True for English
            cn = None
            if card.isnumeric():
                cn = BnToEn(card)
                print(str(cn))
                card = str(cn)
                print("card Number is ", card)
                tracker.slots["card_number"] = card
                if len(card)!=16 or card == None:
                    dispatcher.utter_message(response="utter_invalidCARDnumber")
                    return {"card_number": None}
                else:
                    print("Correct card Number")
                    account = db_manager.set_slot_value(tracker.sender_id, "card_number", card)
                    return {"card_number": card}
        else:
            if len(card)!=16 or card == None:
                dispatcher.utter_message(response="utter_invalidCARDnumber")
                return {"card_number": None}
            else:
                print("Correct card Number")
                account = db_manager.set_slot_value(tracker.sender_id, "card_number", card)
                return {"card_number": card}

# class AffirmOrDenyForDate(Action):
#     """action_check_response_date"""

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "action_check_response_date"

#     async def run(
#         self,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         print(tracker.latest_message['intent'].get('name'))
#         """Executes the action"""
#         print("response check Function Called.")

#         if tracker.latest_message['intent'].get('name') == "affirm":
#             print("Got, Yes")
#             print(tracker.latest_message['intent'].get('name'))
#         if tracker.latest_message['intent'].get('name') == "deny":
#             tracker.slots["Valid_DATE"] = None
#             print(tracker.slots["Valid_DATE"])
#             print(tracker.latest_message['intent'].get('name'))
#             # return [FollowupAction('card_bill_form_c_number')]
#             return [SlotSet("Valid_DATE", None), Form("card_bill_form_V_Date")]

# class ActionCardnumberDATE(FormValidationAction):
#     """validate_card_bill_form_V_Date"""

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "validate_card_bill_form_V_Date"
#     async def validate_Valid_DATE(
#         self,
#         slot_value: Any,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         """Executes the action"""
#         print("validate_Expiry_DATE")
#         card_date = tracker.get_slot("Valid_DATE")
#         print("card expiry date is : ", card_date)
#         currentyear = datetime.datetime.now().year
#         currentmonth = datetime.datetime.now().month
#         print(currentmonth)
#         print(f"this is {currentyear}, and we are not getting smart.")
#         currentyear = str(currentyear)
#         currentyear = currentyear[-2:]
#         currentyear = int(currentyear)
#         print(currentyear)

#         if len(card_date)!=5 or card_date == None:
#             dispatcher.utter_message(response="utter_invalidValid_DATE")
#             return {"Valid_DATE": None}
#         else:
#             expiry_date = str(card_date)
#             print("first 2 digits: ", expiry_date[0:2])
#             month = int(expiry_date[0:2])
#             print("last 2 digit: ", expiry_date[-2:])
#             year = int(expiry_date[-2:])
            
#             if currentyear == year:
#                 if month >= currentmonth:
#                     print("Expiry date is correct.")
#                     account = db_manager.set_slot_value(tracker.sender_id, "Valid_DATE", card_date)
#                     return {"Valid_DATE": card_date}
#                 else:
#                     dispatcher.utter_message(response="utter_invalidValid_DATE")
#                     return {"Valid_DATE": None}
#             elif year > currentyear:
#                 if month> 0 and month<=12:
#                     print("Expiry date is correct.")
#                     account = db_manager.set_slot_value(tracker.sender_id, "Valid_DATE", card_date)
#                     return {"Valid_DATE": card_date}
#                 else:
#                     dispatcher.utter_message(response="utter_invalidValid_DATE")
#                     return {"Valid_DATE": None}
#             else:
#                 dispatcher.utter_message(response="utter_invalidValid_DATE")
#                 return {"Valid_DATE": None}

# class AffirmOrDenyForCCV(Action):
#     """action_check_response_CCV"""

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "action_check_response_CCV"

#     async def run(
#         self,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         print(tracker.latest_message['intent'].get('name'))
#         """Executes the action"""
#         print("response check Function Called.")

#         if tracker.latest_message['intent'].get('name') == "affirm":
#             print("Got, Yes")
#             print(tracker.latest_message['intent'].get('name'))
#         if tracker.latest_message['intent'].get('name') == "deny":
#             tracker.slots["CCV"] = None
#             print(tracker.slots["CCV"])
#             print(tracker.latest_message['intent'].get('name'))
#             # return [FollowupAction('card_bill_form_c_number')]
#             return [SlotSet("CCV", None), Form("card_bill_form_CCV")]

# class ActionCardnumberCCV(FormValidationAction):
#     """validate_card_bill_form_CCV"""

#     def name(self) -> Text:
#         """Unique identifier of the action"""
#         return "validate_card_bill_form_CCV"

#     async def validate_CCV(
#         self,
#         slot_value: Any,
#         dispatcher: CollectingDispatcher,
#         tracker: Tracker,
#         domain: Dict[Text, Any],
#     ) -> List[Dict]:
#         """Executes the action"""
#         ccv = tracker.get_slot("CCV")
#         #BANGLA Check Here
#         if len(ccv)!=3 or ccv == None:
#             dispatcher.utter_message(response="utter_invalidCCV")
#             return {"CCV": None}
#         else:
#             print("Correct CCV Number")
#             self.prev_ccv = ccv
#             account = db_manager.set_slot_value(tracker.sender_id, "CCV", ccv)
#             return {"CCV": ccv}

class ActionCardnumberAMOUNT(FormValidationAction):
    """validate_card_bill_form_amount"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "validate_card_bill_form_amount"
    async def validate_amount_of_money(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
    
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        
        print("CCV in amount validation:", tracker.get_slot("CCV"))
        amount = tracker.get_slot("amount-of-money")
        print("amount inside function: ", amount)

        account_balance = profile_db.get_account_balance(tracker.sender_id)

        number = None
        #BANGLA Check Here
        if(not is_ascii(amount)):  #If Bangla then enter here
            print("Hello, Check Bangla")
            if amount.isnumeric():
                number = BnToEn(amount)
                amount = str(number)
                print("Number : ", number)
                print(amount)
                if(int(amount)<=0):
                    dispatcher.utter_message(response="utter_invalidAMOUNT")
                    # print("1")
                    return {"amount-of-money": None}
                else:
                    # print("2")
                    account = db_manager.set_slot_value(tracker.sender_id, 'amount-of-money', amount)
                    return {"amount-of-money": amount}
            else:
                # print("3")
                return[ SlotSet("amount-of-money", None),
                        ]
        else:
            # print("4")
            if(int(amount)<=0):
                # print("5")
                dispatcher.utter_message(response="utter_invalidAMOUNT")
                return {"amount-of-money": None}
            else:
                account = db_manager.set_slot_value(tracker.sender_id, 'amount-of-money', amount)
                print("Amount is ", amount)
                return {"amount-of-money": amount}

class ResetACNumber(Action):
    """action_reset_account_number"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_account_number"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("Reset Slot Function Called.")
        return[
                SlotSet("account_number", None),
            ]
class ResetPIN(Action):
    """action_reset_PIN"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_PIN"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        """Executes the action"""
        print("Reset Slot Function Called.")
        return[
                SlotSet("PIN", None),
            ]

class ResetPINandACnumer(Action):
    """action_reset_PINandACnumer"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_PINandACnumer"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        """Executes the action"""
        print("Reset AC number and PIN Function Called.")
        return[
                SlotSet("PIN", None),
                SlotSet("account_number", None),
            ]

class AffirmOrDenyACNumber(Action):
    """action_check_AC_Number"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_check_AC_Number"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("response check Function Called.")

        if tracker.latest_message['intent'].get('name') == "affirm":
            print("Got, Yes")
            print(tracker.latest_message['intent'].get('name'))
        if tracker.latest_message['intent'].get('name') == "deny":
            tracker.slots["account_number"] = None
            print(tracker.slots["account_number"])
            print(tracker.latest_message['intent'].get('name'))
            # return [FollowupAction('card_bill_form_c_number')]
            return [SlotSet("account_number", None), Form("check_Balance_ACnum_form")]

class ActionACnumber(FormValidationAction):
    """validate_check_Balance_ACnum_form"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "validate_check_Balance_ACnum_form"

    async def validate_account_number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        
        print("validate_account_number")
        ac = tracker.get_slot("account_number")
        print("AC Number is : ", ac)
        
        #BANGLA Check Here
        if (not is_ascii(ac)):  #If Bangla then enter here. is_ascii(otp) True for English
            cn = None
            if ac.isnumeric():
                cn = BnToEn(ac)
                print(str(cn))
                ac = str(cn)
                print("account Number is ", ac)
                tracker.slots["account_number"] = ac
                if len(ac)!=8 or ac == None:
                    dispatcher.utter_message(response="utter_invalidACNumber")
                    return {"account_number": None}
                else:
                    print("Correct account Number")
                    account = db_manager.set_slot_value(tracker.sender_id, "account_number", ac)
                    return {"account_number": ac}
        else:
            if len(ac)!=8 or ac == None:
                dispatcher.utter_message(response="utter_invalidACNumber")
                return {"account_number": None}
            else:
                print("Correct card Number")
                account = db_manager.set_slot_value(tracker.sender_id, "account_number", ac)
                return {"account_number": ac}

class ActionTellACnumber(Action):

    def name(self) -> Text:
        return "action_tell_ACNumber"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        tell_ACNumber = next(tracker.get_latest_entity_values("account_number"), None)
        
        number=['জিরো','ওয়ান','টু','থ্রি','ফোর','ফাইভ','সিক্স','সেভেন','এইট','নাইন']
        if(tell_ACNumber!=None):
            wr=''
            for c in tell_ACNumber:
                wr=wr+' '+number[int(c)]

        if not tell_ACNumber:
            msg = f"দুঃখিত, আপনার কথাটি বুঝতে পারিনি ।"
            dispatcher.utter_message(text=msg)
            return []

        msg = f"আপনি বলেছেন, {wr} । সেটা ঠিক হলে, হ্যা বলুন ।"
        print('আপনি বলেছেন,', {wr}, '। সেটা ঠিক হলে, হ্যা বলুন ।')
        dispatcher.utter_message(text=msg)
        return []

class AffirmOrDenyPIN(Action):
    """action_check_PIN"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_check_PIN"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("response check Function Called.")

        if tracker.latest_message['intent'].get('name') == "affirm":
            print("Got, Yes")
            print(tracker.latest_message['intent'].get('name'))
        if tracker.latest_message['intent'].get('name') == "deny":
            tracker.slots["PIN"] = None
            print(tracker.slots["PIN"])
            print(tracker.latest_message['intent'].get('name'))
            return [SlotSet("PIN", None), Form("check_Balance_PIN_form")]

class ActionACnumber(FormValidationAction):
    """validate_check_Balance_PIN_form"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "validate_check_Balance_PIN_form"

    async def validate_PIN(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        
        print("validate_PIN")
        pin = tracker.get_slot("PIN")
        print("PIN Number is : ", pin)
        
        #BANGLA Check Here
        if (not is_ascii(pin)):  #If Bangla then enter here. is_ascii(otp) True for English
            cn = None
            if pin.isnumeric():
                cn = BnToEn(pin)
                print(str(cn))
                pin = str(cn)
                print("pin Number is ", pin)
                tracker.slots["PIN"] = pin
                if len(pin)!=4 or pin == None:
                    dispatcher.utter_message(response="utter_invalidPIN")
                    return {"PIN": None}
                else:
                    print("Correct pin Number")
                    account = db_manager.set_slot_value(tracker.sender_id, "PIN", pin)
                    return {"PIN": pin}
        else:
            if len(pin)!=4 or pin == None:
                dispatcher.utter_message(response="utter_invalidPIN")
                return {"PIN": None}
            else:
                print("Correct pin Number")
                account = db_manager.set_slot_value(tracker.sender_id, "PIN", pin)
                return {"PIN": pin}

class ActionShowBalance(Action):
    """Shows the balance of bank or credit card accounts"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_show_balance"

    async def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict
    ) -> List[EventType]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        
        """Executes the custom action"""
        account_type = tracker.get_slot("account_type")

        if account_type == "credit":
            # show credit card balance
            credit_card = tracker.get_slot("credit_card")
            available_cards = profile_db.list_credit_cards(tracker.sender_id)

            if credit_card and credit_card.lower() in available_cards:
                current_balance = profile_db.get_credit_card_balance(
                    tracker.sender_id, credit_card
                )
                dispatcher.utter_message(
                    response="utter_credit_card_balance",
                    **{
                        "credit_card": credit_card.title(),
                        "credit_card_balance": f"{current_balance:.2f}",
                    },
                )
            else:
                for credit_card in profile_db.list_credit_cards(tracker.sender_id):
                    current_balance = profile_db.get_credit_card_balance(
                        tracker.sender_id, credit_card
                    )
                    dispatcher.utter_message(
                        response="utter_credit_card_balance",
                        **{
                            "credit_card": credit_card.title(),
                            "credit_card_balance": f"{current_balance:.2f}",
                        },
                    )
        else:
            # show bank account balance
            account_balance = profile_db.get_account_balance(tracker.sender_id)
            account_balance=str(int(account_balance))
            amount = tracker.get_slot("amount_transferred")
            if amount:
                amount = float(tracker.get_slot("amount_transferred"))
                init_account_balance = account_balance + amount
                dispatcher.utter_message(
                    response="utter_changed_account_balance",
                    init_account_balance=f"{init_account_balance:.2f}",
                    account_balance=f"{account_balance:.2f}",
                )
            else:
                bangla_numeric_string = bangla.convert_english_digit_to_bangla_digit(account_balance)
                print(bangla_numeric_string)

                account_balance=num_convert.number_to_bangla_words(bangla_numeric_string)
                dispatcher.utter_message(
                    response="utter_account_balance",
                    init_account_balance=account_balance,
                )

        events = []
        active_form_name = tracker.active_form.get("name")
        if active_form_name:
            # keep the tracker clean for the predictions with form switch stories
            events.append(UserUtteranceReverted())
            # trigger utter_ask_{form}_AA_CONTINUE_FORM, by making it the requested_slot
            #events.append(SlotSet("AA_CONTINUE_FORM", None))
            # avoid that bot goes in listen mode after UserUtteranceReverted
            events.append(FollowupAction(active_form_name))

        return events


class ActionTellPIN(Action):

    def name(self) -> Text:
        return "action_tell_pin"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        tell_pin = next(tracker.get_latest_entity_values("PIN"), None)
        number=['জিরো','ওয়ান','টু','থ্রি','ফোর','ফাইভ','সিক্স','সেভেন','এইট','নাইন']
        if(tell_pin!=None):
            wr=''
            for c in tell_pin:
                wr=wr+' '+number[int(c)]

        if not tell_pin:
            msg = f"দুঃখিত, আপনার কথাটি বুঝতে পারিনি ।"
            dispatcher.utter_message(text=msg)
            return []

        msg = f"আপনি বলেছেন, {wr} । সেটা ঠিক হলে, হ্যা বলুন ।"
        print('আপনি বলেছেন,', {wr}, '। সেটা ঠিক হলে, হ্যা বলুন ।')
        dispatcher.utter_message(text=msg)
        return []

class ResetBkashTransectionVALUES(Action):
    """action_reset_BkashTransectionVALUES"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_reset_BkashTransectionVALUES"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        """Executes the action"""
        print("Reset bKash related info.")
        return[
                SlotSet("phone_number", None),
                SlotSet("account_number", None),
                SlotSet("amount-of-money", None),
            ]
class ActionACnumber(FormValidationAction):
    """validate_phone_number_form"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "validate_phone_number_form"

    async def validate_phone_number(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        """Executes the action"""
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        
        print("validate_phone_number")
        phone = tracker.get_slot("phone_number")
        print("phone Number is : ", phone)
        
        #BANGLA Check Here
        if (not is_ascii(phone)):  #If Bangla then enter here. is_ascii(otp) True for English
            cn = None
            if phone.isnumeric():
                cn = BnToEn(phone)
                print(str(cn))
                phone = str(cn)
                print("phone Number is ", phone)
                tracker.slots["phone_number"] = phone
                if len(phone)!=11 or phone == None:
                    dispatcher.utter_message(response="utter_invalidphone")
                    return {"phone_number": None}
                else:
                    print("Correct phone Number")
                    account = db_manager.set_slot_value(tracker.sender_id, "phone_number", phone)
                    return {"phone_number": phone}
        else:
            if len(phone)!=11 or phone == None:
                dispatcher.utter_message(response="utter_invalidphone")
                return {"phone_number": None}
            else:
                print("Correct phone Number")
                account = db_manager.set_slot_value(tracker.sender_id, "phone_number", phone)
                return {"phone_number": phone}

class ActionTellphone(Action):

    def name(self) -> Text:
        return "action_tell_PhoneNumber"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        tell_phone = next(tracker.get_latest_entity_values("phone_number"), None)
        number=['জিরো','ওয়ান','টু','থ্রি','ফোর','ফাইভ','সিক্স','সেভেন','এইট','নাইন']
        if(tell_phone!=None):
            wr=''
            for c in tell_phone:
                wr=wr+' '+number[int(c)]

        if not tell_phone:
            msg = f"দুঃখিত, আপনার কথাটি বুঝতে পারিনি ।"
            dispatcher.utter_message(text=msg)
            return []

        msg = f"আপনি বলেছেন, {wr} । সেটা ঠিক হলে, হ্যা বলুন ।"
        print('আপনি বলেছেন,', {wr}, '। সেটা ঠিক হলে, হ্যা বলুন ।')
        dispatcher.utter_message(text=msg)
        return []

class AffirmOrDenyACNumber(Action):
    """action_check_phone_Number"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_check_phone_Number"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("response check phone Function Called.")

        if tracker.latest_message['intent'].get('name') == "affirm":
            print("Got, Yes")
            print(tracker.latest_message['intent'].get('name'))
        if tracker.latest_message['intent'].get('name') == "deny":
            tracker.slots["phone_Number"] = None
            print(tracker.slots["phone_Number"])
            print(tracker.latest_message['intent'].get('name'))
            # return [FollowupAction('card_bill_form_c_number')]
            return [SlotSet("phone_Number", None), Form("phone_number_form")]

class ActionTellamount(Action):

    def name(self) -> Text:
        return "action_tell_Amount"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        tell_amount = next(tracker.get_latest_entity_values("amount-of-money"), None)

        bangla_numeric_string = bangla.convert_english_digit_to_bangla_digit(tell_amount)
        print(bangla_numeric_string)
        account = num_convert.number_to_bangla_words(bangla_numeric_string)

        # number=['জিরো','ওয়ান','টু','থ্রি','ফোর','ফাইভ','সিক্স','সেভেন','এইট','নাইন']
        # if(tell_amount!=None):
        #     wr=''
        #     for c in tell_amount:
        #         wr=wr+' '+number[int(c)]

        if not tell_amount:
            msg = f"দুঃখিত, আপনার কথাটি বুঝতে পারিনি ।"
            dispatcher.utter_message(text=msg)
            return []

        msg = f"আপনি বলেছেন, {account} টাকা। সেটা ঠিক হলে, হ্যা বলুন ।"
        print('আপনি বলেছেন,', {account}, 'টাকা। সেটা ঠিক হলে, হ্যা বলুন ।')
        dispatcher.utter_message(text=msg)
        return []

class AffirmOrDenyACNumber(Action):
    """action_check_amount"""

    def name(self) -> Text:
        """Unique identifier of the action"""
        return "action_check_amount"

    async def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict]:
        print(tracker.latest_message['intent'].get('name'))
        print(tracker.latest_message['intent']['confidence'])
        """Executes the action"""
        print("response check amount Function Called.")

        if tracker.latest_message['intent'].get('name') == "affirm":
            print("Got, Yes")
            print(tracker.latest_message['intent'].get('name'))
        if tracker.latest_message['intent'].get('name') == "deny":
            tracker.slots["amount-of-money"] = None
            print(tracker.slots["amount-of-money"])
            print(tracker.latest_message['intent'].get('name'))
            # return [FollowupAction('card_bill_form_c_number')]
            return [SlotSet("amount-of-money", None), Form("card_bill_form_amount")]