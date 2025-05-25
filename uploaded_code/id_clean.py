from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash, session, Response
import pandas as pd
import sqlite3
import os
import io
import numpy as np
from datetime import datetime
import openpyxl
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.dimensions import SheetFormatProperties
from openpyxl.worksheet.filters import AutoFilter
###########################################################################################################

# ID Function
def pad_to_13_digits(input_string):
    if pd.isna(input_string):
        return input_string
    
    # Check if the input string contains any non-numeric characters
    if not str(input_string).isdigit():
        return input_string
    
    input_length = len(str(input_string))
    
    if input_length < 6:
        padded_string = '0' * (6 - input_length) + str(input_string)
        padded_string = str(padded_string) + '0' * 7
        return padded_string
    elif 6 <= input_length <= 9:
        padded_string = str(input_string) + '0' * (13 - input_length)
        return padded_string
    elif 10 <= input_length < 13:
        padded_string = '0' * (13 - input_length) + str(input_string)
        return padded_string
    else:
        return input_string