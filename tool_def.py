from langchain_core.tools import tool, StructuredTool
import agentql
from playwright.sync_api import sync_playwright

import regex as re

@tool
def login_tool(url: str, username: str, password: str):
    """
        Wait for login action to be completed and new page to load (different url than login)
        Locates web elements via AgentQL (ref: https://docs.agentql.com/agentql-query/query-intro)
        Interacts with retrieved web elements using Playwright and completes user login via provided parameters
    """
    LOGIN_QUERY = """
        {
            username_field
            password_field
            login_button
        }
    """
    with sync_playwright() as playwright, playwright.chromium.launch(headless=False) as browser:
        # Create a new page in the browser and wrap it to get access to AgentQL's querying API
        page = agentql.wrap(browser.new_page())
        page.goto(url)
        # Use query_data() method to fetch the data from the page
        response = page.query_elements(LOGIN_QUERY)
        response.username_field.type(username)
        response.password_field.type(password)
        response.login_button.click()
        # page.wait_for_page_ready_state()
        page.wait_for_timeout(6000)
        new_url = re.findall(r"url='(\S*)'", str(page))[0]
        browser.contexts[0].storage_state(path="avail_login.json")
    return new_url

@tool
def find_and_click_tool(web_element_name: list[str], web_element_type: list[str], url: str):
    """
    Retrieve the login credentials used for login
    Use that as browser context and then search for web elements given in the list on the page
    Once each web element is found, click on it
    Follow the web journey until all web elements have been found and clicked
    """
    with sync_playwright() as playwright, playwright.chromium.launch(headless=False) as browser:
        web_elements_dict = zip(web_element_name, web_element_type)
        web_elements_to_fetch = []
        for item, key in web_elements_dict:
            web_element = item.lower().replace(' ', '_') + '_' + key.lower().replace(' ', '_')
            web_elements_to_fetch.append(web_element)
        # Load the saved signed-in session by creating a new browser context with the saved signed-in state
        context = browser.new_context(storage_state="avail_login.json")
        page = agentql.wrap(context.new_page())
        page.goto(url)
        page.wait_for_page_ready_state()
        page.wait_for_timeout(3000)
        for i in web_elements_to_fetch:
            ELEMENT_QUERY = '{' + '\n' + '\t' + i + '\n' + '\t' + '}'
            response = page.query_elements(ELEMENT_QUERY)
            x = getattr(response, i)
            x.click()
            page.wait_for_timeout(3000)
            new_url = re.findall(r"url='(\S*)'", str(page))[0]
        return new_url

@tool
def fill_form_tool(form_name: str, question_answer: dict[str, str], url: str):
    """
    Find form located in provided url
    Once form is found, find information about all questions it contains, asnwer fields and the type of inputs expected for each
    Then proceed to fill out all the answers as per the input types expected from the provided values
    """
    with sync_playwright() as playwright, playwright.chromium.launch(headless=False) as browser:
        context = browser.new_context(storage_state="avail_login.json")
        form_name = form_name.lower().replace(' ', '_')
        page = agentql.wrap(context.new_page())
        page.goto(url)
        page.wait_for_page_ready_state()
        page.wait_for_timeout(3000)
        # Create query to fetch form data
        FORM_QUERY = '{' + '\n' + '\t' + form_name + '\n' + '\t' + 'questions_answers[]{' + '\n' + '\t\t' + 'question_name'\
             + '\n' + '\t\t' + 'answer_field[]{' + '\t\t\t' + 'name' + '\n' + '\t\t\t' + 'input_type' + '\n' '\t' + '}'*3
        form_data = page.query_data(FORM_QUERY)
        for i in form_data['questions_answers']:
            q_name = i['question_name']
            ans_field_name = i['answer_field'][0]['name']
            ans_field_name = ans_field_name.lower().replace(' ', '_')
            ans_field_ip_type = i['answer_field'][0]['input_type']
            if q_name in question_answer:
                if ans_field_ip_type.lower()!= 'textbox':
                    q_name_for_query = q_name.lower().replace(' ', '_')
                    answer_element_query = "{" + "\n"+ "\t" + q_name_for_query + '_' + ans_field_ip_type + "\n" + "\t" + "}"
                    answer_element = page.query_elements(answer_element_query)
                else:
                    # Create query to fetch web element for answer - to be interacted with later
                    answer_element_query = "{" + "\n"+ "\t" + ans_field_name + "\n" + "\t" + "}"
                    answer_element = page.query_elements(answer_element_query)
                x = getattr(answer_element, ans_field_name)
                match ans_field_ip_type:
                    case 'textbox':
                        x.fill(question_answer[q_name])
                    case 'radio':
                        x.click()
                    case 'checkbox':
                        x.click()
                page.wait_for_timeout(1500)
            else:
                continue
        SUBMIT_BUTTON_QUERY = """
            {
                submit_btn
            }
        """
        submit_button_response = page.query_elements(SUBMIT_BUTTON_QUERY)
        x = getattr(submit_button_response, 'submit_btn')
        x.click()
        page.wait_for_timeout(1500)
        return

# Define the list of tools to be made available to LangGraph model
tools = [
    login_tool,
    find_and_click_tool,
    fill_form_tool
]