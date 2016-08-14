
/*

   Main.js

   Reynir main front-end script

   Author: Vilhjalmur Thorsteinsson
   Copyright (C) 2015
   All rights reserved

*/

// Token identifiers

var TOK_PUNCTUATION = 1;
var TOK_TIME = 2;
var TOK_DATE = 3;
var TOK_YEAR = 4;
var TOK_NUMBER = 5;
var TOK_WORD = 6;
var TOK_TELNO = 7;
var TOK_PERCENT = 8;
var TOK_URL = 9;
var TOK_ORDINAL = 10;
var TOK_TIMESTAMP = 11;
var TOK_CURRENCY = 12;
var TOK_AMOUNT = 13;
var TOK_PERSON = 14;
var TOK_EMAIL = 15;
var TOK_ENTITY = 16;
var TOK_UNKNOWN = 17;

var TOK_P_BEGIN = 10001; // Block begin
var TOK_P_END = 10002; // Block end

var TOK_S_BEGIN = 11001; // Sentence begin
var TOK_S_END = 11002; // Sentence end

var TOK_ERROR_FLAG = 0x10000; // Bit flag to indicate error token

// Punctuation types

var TP_LEFT = 1;
var TP_CENTER = 2;
var TP_RIGHT = 3;
var TP_NONE = 4; // Tight - no whitespace around

// HTML transcoding entities

var entityMap = {
   "&": "&amp;",
   "<": "&lt;",
   ">": "&gt;",
   '"': '&quot;',
   "'": '&#39;',
   "/": '&#x2F;'
};

// Query history
var qHistory = [];

// Waiting for query result?
var queryInProgress = false;


function escapeHtml(string) {
   /* Utility function to properly encode a string into HTML */
   return String(string).replace(/[&<>"'\/]/g, function (s) {
      return entityMap[s];
   });
}

function format_is(n, decimals) {
   /* Utility function to format a number according to is_IS */
   if (decimals === undefined || decimals <= 0)
      return "" + n;
   var s = n.toFixed(decimals);
   return s.replace(/[,.]/g, function (s) {
      return {"," : ".", "." : ","}[s];
   });
}

function nullFunc(json) {
   /* Null placeholder function to use for Ajax queries that don't need a success func */
}

function nullCompleteFunc(xhr, status) {
   /* Null placeholder function for Ajax completion */
}

function errFunc(xhr, status, errorThrown) {
   /* Default error handling function for Ajax communications */
   // alert("Villa í netsamskiptum");
   console.log("Error: " + errorThrown);
   console.log("Status: " + status);
   console.dir(xhr);
}

function serverQuery(requestUrl, jsonData, successFunc, completeFunc, errorFunc) {
   /* Wraps a simple, standard Ajax request to the server */
   $.ajax({
      // The URL for the request
      url: requestUrl,

      // The data to send
      data: jsonData,

      // Whether this is a POST or GET request
      type: "POST",

      // The type of data we expect back
      dataType : "json",

      cache: false,

      // Code to run if the request succeeds;
      // the response is passed to the function
      success: (!successFunc) ? nullFunc : successFunc,

      // Code to run if the request fails; the raw request and
      // status codes are passed to the function
      error: (!errorFunc) ? errFunc : errorFunc,

      // code to run regardless of success or failure
      complete: (!completeFunc) ? nullCompleteFunc : completeFunc
   });
}

function serverPost(url, parameters, new_window) {
   /* Post to the provided URL with the specified parameters */
   var form = $('<form method="post"></form>');
   form.attr("action", url);
   form.attr("target", new_window ? "_blank" : "_self"); // Display in same or new window
   $.each(parameters, function(key, value) {
      var field = $('<input type="hidden"></input>');
      field.attr("name", key);
      field.attr("value", value);
      form.append(field);
   });
   // The form needs to be a part of the document
   // to allow submission, at least in some browsers
   $(document.body).append(form);
   form.submit();
}

var SpeechRecognition = null;
var recognizer = null;

function initializeSpeech() {
   // Attempt to detect and initialize HTML5 speech recognition, if available in the browser
   if (recognizer !== null)
      // Already initialized
      return true;
   SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
   if (SpeechRecognition === null)
      return false;
   recognizer = new SpeechRecognition();
   // Recognizer stops listening when the user pauses
   recognizer.continuous = false;
   recognizer.interimResults = false;
   recognizer.lang = "is-IS";
   // Results of speech recognition
   recognizer.onresult = function(event) {
      var txt = "";
      for (var i = event.resultIndex; i < event.results.length; i++) {
         if (event.results[i].isFinal)
            txt = event.results[i][0].transcript; // + ' (Confidence: ' + event.results[i][0].confidence + ')';
         else
            txt += event.results[i][0].transcript;
      }
      $("#url").val(txt);
      $("#url").attr("placeholder", "");
      $("#microphone").removeClass("btn-danger").addClass("btn-info");
      // Send the query to the server
      analyzeQuery();
   };
   // Listen for errors
   recognizer.onerror = function(event) {
      var txt = "Hljóðnemi virkar ekki" + (event.message.length ? (" (" + event.message + ")") : "");
      $("#url").val(txt);
      $("#url").attr("placeholder", "");
      $("#microphone").removeClass("btn-danger").addClass("btn-info");
   };
   // Successfully initialized
   return true;
}

function showParse(ev) {
   /* A sentence has been clicked: show its parse grid */
   var sentText = $(ev.delegateTarget).text();
   // Do an HTML POST to the parsegrid URL, passing
   // the sentence text within a synthetic form
   serverPost("/parsegrid", { txt: sentText, debug: debugMode() }, false)
}

function buttonOver(elem) {
   /* Show a hover effect on a button */
   if (!$(elem).hasClass("disabled"))
      $(elem).toggleClass("over", true);
}

function buttonOut(elem) {
   /* Hide a hover effect on a button */
   $(elem).toggleClass("over", false);
}

function lzero(n, field) {
   return ("0000000000" + n).slice(-field);
}

function iso_date(d) {
   // Format a date as an ISO string
   return lzero(d[0], 4) + "-" + lzero(d[1], 2) + "-" + lzero(d[2], 2);
}

function iso_timestamp(d) {
   // Format a date + time as an ISO string
   return lzero(d[0], 4) + "-" + lzero(d[1], 2) + "-" + lzero(d[2], 2) + " " +
      lzero(d[3], 2) + ":" + lzero(d[4], 2) + ":" + lzero(d[5], 2);
}

function hoverIn() {
   // Hovering over a token
   var wId = $(this).attr("id");
   if (wId === null || wId === undefined)
      // No id: nothing to do
      return;

   var ix = parseInt(wId.slice(1));
   var out = $("div#result");
   var tokens = out.data("tokens");
   var nameDict = out.data("nameDict"); // Can be null
   var wl = tokens[ix];
   var offset = $(this).position();
   var left = offset.left;
   var i;
   var gender;
   var info = $("div.info");

   // Highlight the token
   $(this).addClass("highlight");

   if (wl[0] == TOK_WORD) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Word: list its potential meanings
      for (i = 0; i < wl[2].length; i++) {
         var form = wl[2][i];
         info.append("<p>" + form[2] + " <b>" + form[0] + "</b> <i>" + form[5] + "</i></p>");
      }
   }
   else
   if (wl[0] == TOK_NUMBER) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show the parsed floating-point number to 2 decimal places
      gender = (wl[2][2] !== null) ? (" " + wl[2][2]) : "";
      info.append("<p>" + wl[2][0].toFixed(2) + gender + "</p>");
      // Show cases, if available
      if (wl[2][1] !== null)
         for (i = 0; i < wl[2][1].length; i++)
            info.append("<p>" + wl[2][1][i] + "</p>");
   }
   else
   if (wl[0] == TOK_PERCENT) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show the parsed floating-point number to 1 decimal place
      gender = (wl[2][2] !== null) ? (" " + wl[2][2]) : "";
      info.append("<p>" + wl[2][0].toFixed(1) + "% " + gender + "</p>");
      // Show cases, if available
      if (wl[2][1] !== null)
         for (i = 0; i < wl[2][1].length; i++)
            info.append("<p>" + wl[2][1][i] + "</p>");
   }
   else
   if (wl[0] == TOK_ORDINAL) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show the parsed number
      info.append("<p>" + wl[2] + "</p>");
   }
   else
   if (wl[0] == TOK_DATE) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show the date in ISO format
      info.append("<p>" + iso_date(wl[2]) + "</p>");
   }
   else
   if (wl[0] == TOK_CURRENCY) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show the ISO code for the currency
      info.append("<p>" + wl[2][0] + "</p>");
      // Show cases, if available
      if (wl[2][1] !== null)
         for (i = 0; i < wl[2][1].length; i++)
            info.append("<p>" + wl[2][1][i] + "</p>");
   }
   else
   if (wl[0] == TOK_AMOUNT) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show the amount as well as the ISO code for its currency
      gender = (wl[2][3] !== null) ? (" " + wl[2][3]) : "";
      info.append("<p>" + wl[2][1] + " " + wl[2][0].toFixed(2) + gender + "</p>");
      // Show cases, if available
      if (wl[2][2] !== null)
         for (i = 0; i < wl[2][2].length; i++)
            info.append("<p>" + wl[2][2][i] + "</p>");
   }
   else
   if (wl[0] == TOK_PERSON) {
      if (!wl[2].length)
         info.html("<p><b>" + wl[1] + "</b></p>");
      else {
         var p = wl[2][0];
         // Show name and title
         var name = p[0];
         var title = nameDict ? (nameDict[name] || "") : "";
         info.html("<p><b>" + name + "</b> " + title + "</p>");
      }
   }
   else
   if (wl[0] == TOK_ENTITY) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show definitions, if any
      if (wl[2][0].length) {
         info.append("<ul>");
         for (i = 0; i < wl[2][0].length; i++)
            info.append("<li>" + wl[2][0][i][0] + " " + wl[2][0][i][1] + "</li>");
         info.append("</ul>");
      }
   }
   else
   if (wl[0] == TOK_TIMESTAMP) {
      info.html("<p><b>" + wl[1] + "</b></p>");
      // Show the timestamp in ISO format
      info.append("<p>" + iso_timestamp(wl[2]) + "</p>");
   }
   info
      .css("top", offset.top.toString() + "px")
      .css("left", left.toString() + "px")
      .css("visibility", "visible");
}

function hoverOut() {
   // Stop hovering over a word
   $("div.info").css("visibility", "hidden");
   $(this).removeClass("highlight");
}

function populateMetadata(m) {
   // Display the article metadata, if any
   if (m === null) {
      // No metadata: hide it
      $("#metadata").css("display", "none");
      return;
   }
   $("#meta-heading").text(m.heading);
   $("#meta-author").text(m.author);
   $("#meta-timestamp").text(m.timestamp);
   var ref = $("<a></a>").attr("href", m.url).attr("target", "_blank").text("Upphafleg grein")
      .append($("<img></img>").attr("src", "/static/" + m.icon).attr("width", 16).attr("height", 16));
   $("#meta-url").html(ref);
   // $("#meta-authority").text(m.authority.toFixed(1));
   $("#metadata").css("display", "block");
}

function add_w(wsp, cls, i, wrd) {
   // Add HTML for a single word to s
   return wsp + "<i class='" + cls + "' id='w" + i + "'>" + wrd + "</i>";
}

function populateRegister(register) {
   // Populate the name register display
   var count = 0;
   var i, item, name, title;
   $("#namelist").html("");
   if (register !== null && register.length > 0) {
      for (i = 0; i < register.length; i++) {
         item = $("<li></li>");
         name = $("<span></span>").addClass("name").text(register[i].name);
         title = $("<span></span>").addClass("title").text(register[i].title);
         item.append(name);
         item.append(title);
         $("#namelist").append(item);
         count++;
      }
   }
   // Display the register
   if (count) {
      $("#register").css("display", "block");
      $("#namelist span.name").click(function(ev) {
         // Send a query to the server
         queryPerson($(this).text());
      });
   }
}

function handleError(xhr, status, errorThrown) {
   /* An error occurred on the server or in the communications */
   // Hide progress indicator
   wait(false);
   $("div#result").html("<div class='guide-empty'><p><b>Villa kom upp</b> í samskiptum við netþjón Greynis</p></div>");
}

function handleQueryError(xhr, status, errorThrown) {
   /* An error occurred on the server or in the communications */
   // Hide progress indicator
   wait(false);
   $("div#entity-body").html("<div class='guide-empty'><p><b>Villa kom upp</b> í samskiptum við netþjón Greynis</p></div>");
}

function showPerson(ev) {
   // Send a query to the server
   var wId = $(this).attr("id"); // Check for token id
   var name;
   if (wId === undefined)
      name = $(this).text(); // No associated token: use the contained text
   else {
      // Obtain the name in nominative case from the token
      var ix = parseInt(wId.slice(1));
      var out = $("div#result");
      var tokens = out.data("tokens");
      var wl = tokens[ix];
      if (!wl[2].length)
         name = wl[1];
      else
         name = wl[2][0][0];
   }
   queryPerson(name);
   ev.stopPropagation();
}

function showEntity(ev) {
   // Send a query to the server
   queryEntity($(this).text());
   ev.stopPropagation();
}

function makeNameDict(register) {
   // Make a name dictionary from a name register list
   var nameDict = { };
   if (register !== null && register.length > 0)
      for (var i = 0; i < register.length; i++)
         nameDict[register[i].name] = register[i].title;
   return nameDict;
}

function populateDisplayResult(json) {
   // Show the result of a display request for an existing article
   // Hide progress indicator
   wait(false);
   populateMetadata(json.result.metadata);
   // Show the statistics
   $("div#statistics").css("display", "block");
   populateRawResult(json);
}

function populateTextResult(json) {
   // Display the results of analysis by the server
   wait(false);
   // Show the output
   $("div#output").css("display", "block");
   // Show the statistics
   $("div#statistics").css("display", "block");
   populateRawResult(json);
}

function populateRawResult(json) {
   // Populate the result div with token info
   var out = $("div#result");
   var tokens = json.result.tokens;
   var register = json.result.register || null; // Name register
   out.data("tokens", tokens);
   out.data("nameDict", makeNameDict(register));
   // Update key statistics
   $("#tok-num").text(json.result.tok_num);
   $("#num-sent").text(json.result.num_sent);
   $("#num-parsed-sent").text(json.result.num_parsed_sent);
   var ratio = 0.0;
   if (json.result.num_sent)
      ratio = json.result.num_parsed_sent / json.result.num_sent * 100;
   $("#num-parsed-ratio").text(format_is(ratio, 1));
   $("#avg-ambig-factor").text(format_is(json.result.avg_ambig_factor, 2));
   // Process token list
   var i;
   var s = "";
   var wsp = ""; // Pending whitespace
   for (i = 0; i < tokens.length; i++) {
      var wl = tokens[i];
      var wl0 = wl[0];
      if (wl0 & TOK_ERROR_FLAG) {
         // The token has earlier been marked as an error token:
         // enclose it within a span identifying it as such
         wl0 &= ~TOK_ERROR_FLAG;
         if (wl0 == TOK_S_BEGIN || wl0 == TOK_P_BEGIN || wl0 == TOK_S_END || wl0 == TOK_P_END) {
            // Can't mark this token as an error token as it starts or ends a <span> or <p>
            wl[0] &= ~TOK_ERROR_FLAG;
         }
         else {
            if (wl0 != TOK_PUNCTUATION) {
               s += wsp;
               wsp = "";
            }
            s += "<span class='errtok'>";
         }
      }
      if (wl0 == TOK_PUNCTUATION) {
         if (wl[2] == TP_LEFT) {
            // Left associative punctuation
            s += wsp + wl[1];
            wsp = "";
         }
         else
         if (wl[2] == TP_RIGHT) {
            s += wl[1]; // Keep pending whitespace unchanged
         }
         else
         if (wl[2] == TP_CENTER) {
            // Whitespace on both sides
            s += wsp + wl[1];
            wsp = " ";
         }
         else
         if (wl[2] == TP_NONE) {
            // Tight: no whitespace
            if (wl[1] == "-")
               s += "–"; // Replace hyphen with En dash
            else
               s += wl[1];
            wsp = "";
         }
      }
      else
      if (wl0 == TOK_WORD) {
         if (wl[2] === null || wl[2].length == 0)
            // Word not recognized
            s += wsp + "<i class='nf'>" + wl[1] + "</i>";
         else
            s += wsp + "<i id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl0 == TOK_P_BEGIN) {
         s += "<p>";
         wsp = "";
      }
      else
      if (wl0 == TOK_P_END) {
         if (s.slice(-3) == "<p>")
            // Avoid empty <p></p>
            s = s.slice(0, -3);
         else
            s += "</p>";
         wsp = "";
      }
      else
      if (wl0 == TOK_S_BEGIN) {
         var c = "sent";
         var nump = wl[2][0];
         var errIndex = wl[2][1]; // Index of error token if nump == 0
         if (nump === 0 && errIndex !== null)
            // Mark the error token with an error flag
            tokens[i + 1 + errIndex][0] |= TOK_ERROR_FLAG;
         if (nump > 0)
            // This sentence has at least one parse tree: mark it
            c += " parsed";
         else
            c += " err";
         /*
         if (nump > 100)
            // This sentence has a lot of parses: mark it
            c += " very-ambig";
         */
         s += "<span class='" + c + "'>";
         wsp = "";
      }
      else
      if (wl0 == TOK_S_END) {
         if (s.slice(-6) == "<span>")
            // Avoid empty <span></span>
            s = s.slice(0, -6);
         else
            s += "</span>";
         // Keep pending whitespace unchanged
      }
      else
      if (wl0 == TOK_NUMBER) {
         s += add_w(wsp, "number", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_PERCENT) {
         s += add_w(wsp, "percent", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_ORDINAL) {
         s += add_w(wsp, "ordinal", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_DATE) {
         s += add_w(wsp, "date", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_TIMESTAMP) {
         s += add_w(wsp, "timestamp", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_CURRENCY) {
         s += add_w(wsp, "currency", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_AMOUNT) {
         s += add_w(wsp, "amount", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_PERSON) {
         s += add_w(wsp, "person", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_ENTITY) {
         s += add_w(wsp, "entity", i, wl[1]);
         wsp = " ";
      }
      else
      if (wl0 == TOK_YEAR || wl0 == TOK_TELNO || wl0 == TOK_EMAIL || wl0 == TOK_TIME) {
         s += wsp + "<b>" + wl[1] + "</b>";
         wsp = " ";
      }
      else
      if (wl0 == TOK_UNKNOWN) {
         // Token not recognized
         s += wsp + "<i class='nf'>" + wl[1] + "</i>";
         wsp = " ";
      }
      if (wl[0] & TOK_ERROR_FLAG) {
         s += "</span>";
         // Remove the flag when we're done with it
         wl[0] &= ~TOK_ERROR_FLAG;
      }
   }
   out.html(s);
   // Put a hover handler on each word
   $("div#result i").hover(hoverIn, hoverOut);
   // Put a click handler on each sentence
   $("span.sent").click(showParse);
   // Separate click handler on entity names
   $("i.entity").click(showEntity);
   // Separate click handler on person names
   $("i.person").click(showPerson);
   populateRegister(register);
}

function clearResult() {
   // Clear previous result
   $("div#result").html("");
   // Display progress indicator
   wait(true);
   // Make the statistics appear but hidden until processing is complete
   $("div#statistics").css("display", "none");
   // Hide the metadata
   $("#metadata").css("display", "none");
   // Hide the register
   $("div#register").css("display", "none");
}

function populateQueryResult(json) {
   // Display the result of a query sent to the server
   // Hide progress indicator
   wait(false);
   var r = json.result;
   var q = $("<h3 class='query'></h3>");
   q.text(r.q);
   var image = $("<p class='image'></p>");
   var answer;
   if (r.is_query) {
      // This is a valid query response: present the response items in a bulleted list
      if (r.image !== undefined) {
         // The response contains an image: insert it
         image = image.html(
            $("<a></a>").attr("href", r.image.link).html(
               $("<img></img>")
                  .attr("src", r.image.src)
                  .attr("width", r.image.width)
                  .attr("height", r.image.height)
                  .attr("title", r.image.origin)
            )
         );
      }
      answer = $("<ul></ul>");
      if (!r.response || !r.response.length)
         answer = $("<p class='query-empty'></p>")
            .html("<span class='red glyphicon glyphicon-play'></span>&nbsp;Ekkert svar fannst.");
      else {
         $.each(r.response, function(i, obj) {
            var li;
            if (r.qtype == "Title")
               // For person names, generate a 'name' span
               li = $("<li></li>").html($("<span class='name'></span>").text(obj[0]));
            else
               li = $("<li></li>").text(obj[0]);
            var urlList = obj[1];
            var artList = li.append($("<span class='art-list'></span>")).children().last();
            for (var i = 0; i < urlList.length; i++) {
               var u = urlList[i];
               artList.append($("<span class='art-link'></span>")
                  .attr("title", u[2])
                  .attr("data-uuid", u[1])
                  .html($("<img width='16' height='16'></img>").attr("src", "/static/" + u[0] + ".ico"))
               );
            }
            answer.append(li);
         });
      }
   }
   else {
      // An error occurred
      answer = $("<p class='query-error'></p>");
      if (r.error === undefined)
         answer.html("<span class='red glyphicon glyphicon-play'></span>&nbsp;")
            .append("Þetta er ekki fyrirspurn sem Greynir skilur. ")
            .append($("<a></a>").attr("href", "/analysis?txt=" + r.q).text("Smelltu hér til að málgreina."));
      else
         answer.html("<span class='red glyphicon glyphicon-play'></span>&nbsp;")
            .text(r.error);
   }
   $("#entity-body").html(q).append(image).append(answer);
   // A title query yields a list of names
   // Clicking on a name submits a query on it
   $("#entity-body span.name").click(showPerson);
   $("span.art-link").click(function(ev) {
      // Show a source article
      window.location.href = "/page?id=" + $(this).attr("data-uuid");
   });
}

function clearQueryResult() {
   // Clear previous result
   $("div#entity-body").html("");
   // Display progress indicator
   wait(true);
}

function updateBackButton() {
   // Update the state of the back button after modifying the history
   var disable = (qHistory.length < 2) || queryInProgress;
   if (disable)
      $("#back").attr("disabled", "disabled");
   else
      $("#back").removeAttr("disabled");
   if (disable)
      $("#back").attr("title", "");
   else
      // Show the query that we would go back to
      $("#back").attr("title", qHistory[qHistory.length - 2].q);
}

// Actions encoded in URLs
var urlToFunc = {
   "q" : _submitQuery,
   "d" : _displayUrl
};

var funcToUrl = {
   _submitQuery : "q",
   _displayUrl : "d"
};

function addHistory(func, q) {
   // Add an item to the query qHistory
   if (qHistory.length && qHistory[qHistory.length - 1].q == q)
      // Same query as we have already: don't push again
      return;
   var state = { f: funcToUrl[func], q : q };
   qHistory.push(state);
   history.pushState(state, "",
      "?f=" + state.f + "&q=" + encodeURIComponent(state.q));
   updateBackButton();
}

function backHistory() {
   // Go back one step in the query qHistory
   if (qHistory.length < 2)
      // Nothing to go back to
      return;
   qHistory.pop(); // Pop off the state where we already are
   var h = qHistory[qHistory.length - 1]; // Get the previous state
   $("#url").val(h.q); // Go back to original query string
   history.replaceState(h, "", "?f=" + h.f + "&q=" + encodeURIComponent(h.q));
   updateBackButton();
   // Execute the original query function again
   urlToFunc[h.f](h.q);
}

function navToHistory(func, q) {
   if (urlToFunc[func] === undefined)
      // Invalid function
      return;
   // Navigate to a previous state encoded in a URL
   $("#url").val(q); // Go back to original query string
   var state = { f: func, q : q };
   qHistory.push(state);
   // Execute the original query function again
   urlToFunc[func](q);
}

function analyzeText(txt) {
   // Ask the server to tokenize and parse the given text
   clearResult();
   // Launch the query
   serverQuery('/analyze.api', // Endpoint with .api suffix are not cached
      {
         url : txt,
         noreduce : true,
         autouppercase : false
      },
      populateTextResult,
      null,
      handleError
   );
}

function _displayUrl(url) {
   clearResult();
   // Launch the query
   serverQuery('/display.api',
      {
         url : url
      },
      populateDisplayResult, // successFunc
      null, // completeFunc
      handleError // errorFunc
   );
}

function displayUrl(url) {
   if (queryInProgress)
      // Already waiting on a query
      return;
   // Ask the server to display an already scraped, tokenized and parsed article
   $("#url").val(url); // Show URL in the input field
   addHistory("_displayUrl", url);
   _displayUrl(url);
}

function _submitQuery(q) {
   clearQueryResult();
   // Launch the query
   serverQuery('/query.api',
      { q : q }, // Query string
      populateQueryResult, // successFunc
      null, // completeFunc
      handleQueryError // error Func
   );
}

function analyzeQuery() {
   // Submit the query in the url input field to the server
   if (queryInProgress)
      // Already waiting on a query
      return;
   var q = $("#url").val().trim();
   if (q.startsWith("http://") || q.startsWith("https://")) {
      wait(true); // Show spinner while loading page
      window.location.href = "/page?url=" + encodeURIComponent(q);
      return;
   }
   addHistory("_submitQuery", q);
   _submitQuery(q);
}

function submitQuery(q) {
   // Submit the given query to the server
   if (queryInProgress)
      // Already waiting on a query
      return;
   $("#url").val(q); // Show the query in the input field
   addHistory("_submitQuery", q);
   _submitQuery(q);
}

function queryPerson(name) {
   // Navigate to the main page with a person query
   window.location.href = "/?f=q&q=" + encodeURIComponent("Hver er " + name + "?");
}

function queryEntity(name) {
   // Navigate to the main page with an entity query
   window.location.href = "/?f=q&q=" + encodeURIComponent("Hvað er " + name + "?");
}

function urldecode(s) {
   return decodeURIComponent(s.replace(/\+/g, '%20'));
}

function getUrlVars() {
   // Obtain query parameters from the URL
   var vars = [];
   var ix = window.location.href.indexOf('?');
   if (ix >= 0) {
      var hash;
      var hashes = window.location.href.slice(ix + 1).split('&');
      for (var i = 0; i < hashes.length; i++) {
         hash = hashes[i].split('=');
         vars.push(hash[0]);
         vars[hash[0]] = urldecode(hash[1]);
      }
   }
   return vars;
}

function initMain(jQuery) {
   // Initialization
   // Set up event handlers
   $("#url")
      .click(function(ev) {
         this.setSelectionRange(0, this.value.length);
      })
      .keydown(function(ev) {
         if (ev.which == 13) {
            analyzeQuery();
            ev.preventDefault();
         }
      });

   // Initialize the back button
   $("#back").click(function(ev) { backHistory(); });
   updateBackButton();

   if (initializeSpeech()) {
      // Speech input seems to be available
      $("#microphone-div").css("display", "block");
      // Make the URL input box smaller to accommodate the microphone
      $("#url-div")
         .removeClass("col-xs-7").removeClass("col-sm-9")
         .addClass("col-xs-5").addClass("col-sm-8");
      // Enable the microphone button to start the speech recognizer
      $("#microphone").click(function(ev) {
         $("#url").val("");
         $("#url")
            .attr("placeholder", "Talaðu í hljóðnemann! Til dæmis: Hver er seðlabankastjóri?");
         $(this)
            .removeClass("btn-info")
            .addClass("btn-danger");
         recognizer.start();
      });
   }

   // Check whether a query was encoded in the URL
   var rqVars = getUrlVars();
   if (rqVars.f !== undefined && rqVars.q !== undefined)
      // We seem to have a legit query URL
      navToHistory(rqVars.f, rqVars.q);

   // Select all text in the url input field
   $("#url").get(0).setSelectionRange(0, $("#url").val().length);

   // Clicking in italic words in the guide
   $("div.guide-empty i").click(function(ev) {
      window.location.href = "/?f=q&q=" + encodeURIComponent($(this).text());
   });

   // Activate the top navbar
   $("#navid-main").addClass("active");
}

