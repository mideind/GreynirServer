
/*

   Main.js

   Reynir front page script

   Author: Vilhjalmur Thorsteinsson
   Copyright (C) 2016
   All rights reserved

*/


// Query history
var qHistory = [];

// Waiting for query result?
var queryInProgress = false;


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

function handleQueryError(xhr, status, errorThrown) {
   /* An error occurred on the server or in the communications */
   // Hide progress indicator
   wait(false);
   $("div#entity-body").html("<div class='guide-empty'><p><b>Villa kom upp</b> í samskiptum við netþjón Greynis</p></div>");
}

function queryPerson(name) {
   // Navigate to the main page with a person query
   window.location.href = "/?f=q&q=" + encodeURIComponent("Hver er " + name + "?");
}

function queryEntity(name) {
   // Navigate to the main page with an entity query
   window.location.href = "/?f=q&q=" + encodeURIComponent("Hvað er " + name + "?");
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

function correctPlural(c, one, singular, plural) {
   // Yield a correct plural/singular text corresponding to number c
   if (c == 1)
      return one + " " + singular; // einni grein
   if ((c % 10 == 1) && (c != 11))
      // 21 grein, 131 grein
      return c.toString() + " " + singular;
   // 11 greinum, 7 greinum
   return c.toString() + " " + plural;
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
      var rlist;
      if (r.qtype == "Word") {
         rlist = r.response.rlist;
         if (rlist && rlist.length) {
            var c = r.response.acnt;
            var g = correctPlural(c, "einni", "grein", "greinum");
            answer = $("<p></p>").text("'" + r.key + "' kemur fyrir í " + g + ", ásamt eftirtöldum orðum:")
               .append($("<ul></ul>"));
         }
      }
      else
         rlist = r.response;
      if (!rlist || !rlist.length)
         answer = $("<p class='query-empty'></p>")
            .html("<span class='red glyphicon glyphicon-play'></span>&nbsp;Ekkert svar fannst.");
      else {
         $.each(rlist, function(i, obj) {
            var li;
            if (r.qtype == "Word") {
               if (obj.cat.startsWith("person_"))
                  li = $("<li></li>").html($("<span class='name'></span>").text(obj.stem));
               else
               if (obj.cat.startsWith("entity") || obj.cat.startsWith("sérnafn"))
                  li = $("<li></li>").html($("<span class='entity'></span>").text(obj.stem));
               else
                  li = $("<li></li>").text(obj.stem + " ").append($("<small></small>").text(obj.cat));
            }
            else {
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
   $("#entity-body span.entity").click(showEntity);
   $("span.art-link").click(function(ev) {
      // Show a source article
      wait(true); // This can take time, if a parse is required
      $("#url").val("Málgreining í gangi...");
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
   "q" : _submitQuery
};

var funcToUrl = {
   _submitQuery : "q"
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

