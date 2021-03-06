#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Oct 12 15:40:26 2020

@author: villa
"""

import re
import os
import os.path as op
import json


def change_file (input_file , output_file=None, back_up_file = True,
                 str_to_modify = {}, lines_to_add=[], check_added_lines = True, lines_to_remove = []):
    
    ''' function to generate a copy of a file changing a string in specific lines
         In case input and output files are the same a copy of the old file is 
         created with name 'old_{input_file}'
    
     input_file: input file to change
     output_file: output file to generate
                  - Default is 'None' - in this case the same is set equal as the input file
                  - In case output_file and input_file have the same name a copy of 
                    the original input file is saved
     str_to_modify: dictionary of strings to be modified - format: {'old string':'new string'}
     lines_to_add: list of lines to be added at the end of the file: format: ['string 1','string 2']
     check_added_lines: - True - if line is already present is not added
                        - False - line is added indipendently of the others
    ''' 
    origin_file = open(input_file,'r')
    lines_list = origin_file.readlines()
    origin_file.close()
    
    if output_file == None or input_file == output_file:
        output_file = input_file
        if back_up_file == True:
            os.rename(input_file, 'old_' + input_file) 
        else:
            os.remove(input_file)
    
    new_file = open(output_file,'w')
           
    for line in lines_list:        
        rem_line = False
        mod_line = False 
        for l in lines_to_remove:
            if l + '\n' == line:
                rem_line = True
        for string in str_to_modify: 
            target_line = re.findall(string, line)                      
            if target_line != [] and rem_line == False:
                new_file.write(line.replace(string,str_to_modify[string]))
                mod_line = True                  
        if mod_line == False and rem_line == False:
             new_file.write(line)   
         
    for l in lines_to_add:
          if check_added_lines:              
              if l + '\n' not in lines_list:            
                  new_file.write(l + '\n')
          else:
              new_file.write(l + '\n')
    
    new_file.close()
    
    return
    


def get_object_from_json(cls,path_or_string):
    """
    Build class object from json file or string. The class must posses the 'from_dict' method.

    Parameters
    ----------
    cls : (class)
    path_or_string : (str)
        If an existing path to a file is given the object is constructed reading the json file.
        Otherwise it will be read as a string.

    Returns
    -------
    PhaseDiagram object.

    """
    if op.isfile(path_or_string):
        with open(path_or_string) as file:
            d = json.load(file)
    else:
        d = json.load(path_or_string)

    return cls.from_dict(d)


def save_object_as_json(object,path):
    """
    Save class object as json string or file. The class must posses the 'as_dict' method.

    Parameters
    ----------
    object: object of a class
    path : (str)
        Path to the destination file.  If None a string is exported.

    Returns
    -------
    d : (str)
        If path is not set a string is returned.
    """
    d = object.as_dict()
    if path:
        with open(path,'w') as file:
            json.dump(d,file)
        return
    else:
        return d.__str__() 



def grep(search_string,file):    
    '''
    Function that emulates "grep" function and returns a list of lines
    that contain target string
    '''         
    lines = []    
    with open (file,'r') as origin_file:
    # searching lines in input file   
        for line in origin_file:
       # emulating 'grep' command
            target_line = re.findall(search_string, line)
            if target_line:
                lines.append(line)
        return lines
         

def grep_list(search_string,target_list):
    """
    Search string in a list of strings. Returns lines that contain the searched string.
    """
    lines=[]
    for l in target_list:
        if search_string in l:
            lines.append(l)
            
    return lines