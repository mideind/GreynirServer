def getHouseholds():
    """
    Returns the list of households of the user
    """
    url = "https://api.ws.sonos.com/control/api/v1/households"

    payload = {}
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.text)


def getGroups():
    """
    Returns the list of groups of the user
    """
    url = "https://api.ws.sonos.com/control/api/v1/households/Sonos_2qmmZYj1IfZpziI3yTZT2AdYkP.LzZPKytb_zgm6t3fVIv7/groups"

    payload = {}
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request("GET", url, headers=headers, data=payload)

    print(response.text)


def createToken(code):
    """
    Creates a token given a code
    """
    url = f"https://api.sonos.com/login/v3/oauth/access?grant_type=authorization_code&code={code}&redirect_uri=http://localhost:5000/connect_sonos.api"

    payload = {}
    headers = {
        "Authorization": f"Basic {sonos_encoded_credentials}",
        "Cookie": "JSESSIONID=F710019AF0A3B7126A8702577C883B5F; AWSELB=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171; AWSELBCORS=69BFEFC914A689BF6DC8E4652748D7B501ED60290D5EA56F2E543ABD7CF357A5F65186AEBCFB059E28075D83A700FD504C030A53CC28683B515BE3DCA3CC587AFAF606E171",
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.text)
