def getHouseholds(token):
    """
    Returns the list of households of the user
    """
    url = "https://api.ws.sonos.com/control/api/v1/households"

    payload = {}
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request("GET", url, headers=headers, data=payload)

    return response


def getGroups(houshold_id, token):
    """
    Returns the list of groups of the user
    """
    url = "https://api.ws.sonos.com/control/api/v1/households/{household_id}/groups"

    payload = {}
    headers = {"Authorization": f"Bearer {token}"}

    response = requests.request("GET", url, headers=headers, data=payload)

    return response


def createToken(code, sonos_encoded_credentials):
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

    return response


def togglePlayPause(group_id, token):
    """
    Toggles the play/pause of a group
    """
    url = (
        f"https://api.ws.sonos.com/control/api/v1/groups/{group_id}/playback/playPause"
    )

    payload = {}
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    response = requests.request("POST", url, headers=headers, data=payload)

    return response
