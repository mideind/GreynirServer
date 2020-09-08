/*

   Main.js

   Greynir front page script

    Copyright (C) 2018 Miðeind ehf.

       This program is free software: you can redistribute it and/or modify
       it under the terms of the GNU General Public License as published by
       the Free Software Foundation, either version 3 of the License, or
       (at your option) any later version.
       This program is distributed in the hope that it will be useful,
       but WITHOUT ANY WARRANTY; without even the implied warranty of
       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
       GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see http://www.gnu.org/licenses/.

*/

"use strict";

// Waiting for query result?
var queryInProgress = false;

function formatReal(n, decimals) {
   // Return the number n formatted correctly for the Icelandic locale
   return n.toFixed(decimals).replace(".", ",");
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

var SpeechRecognition = null;
var recognizer = null;

function initializeSpeech() {
   // Attempt to detect and initialize HTML5 speech recognition, if available in the browser
   if (recognizer !== null) {
      // Already initialized
      return true;
   }
   SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition || null;
   if (SpeechRecognition === null) {
      return false;
   }
   recognizer = new SpeechRecognition();
   // Recognizer stops listening when the user pauses
   recognizer.continuous = false;
   recognizer.interimResults = false;
   recognizer.lang = "is-IS";
   recognizer.maxAlternatives = 10;
   // Results of speech recognition
   recognizer.onresult = function(event) {
      var txt = "";
      var first = "";
      for (var i = event.resultIndex; i < event.results.length; i++) {
         if (event.results[i].isFinal) {
            // Accumulate top results
            for (var j = 0; j < event.results[i].length; j++) {
               // Note top suggestion to place in query input field
               if (j === 0) {
                  first = event.results[i][j].transcript;
               }
               txt += event.results[i][j].transcript + "|"
            }
         }
         else {
            txt += event.results[i][0].transcript;
         }
      }
      $("#url").val(first);
      $("#url").attr("placeholder", "");
      $("#microphone").removeClass("btn-danger").addClass("btn-success");
      // Send the query to the server
      analyzeQuery({ q: txt, autouppercase: true }); // Ask for auto-uppercasing
   };
   // Listen for errors
   recognizer.onerror = function(event) {
      var txt = "Hljóðnemi virkar ekki" + (event.message.length ? (" (" + event.message + ")") : "");
      $("#url").val(txt);
      $("#url").attr("placeholder", "");
      $("#microphone").removeClass("btn-danger").addClass("btn-success");
   };
   // Successfully initialized
   return true;
}

function wait(state) {
   // Start or stop a wait spinner
   queryInProgress = state;
   if (state) {
      $("#url-ok").attr("disabled", "disabled")
         .html("<span class='glyphicon glyphicon-restart glyphicon-spin-white'></span>");
      $("#microphone").attr("disabled", "disabled");
      $("div.guide-empty").css("display", "none");
   }
   else {
      $("#url-ok").removeAttr("disabled").text("Greina");
      $("#microphone").removeAttr("disabled");
   }
}

function handleQueryError(xhr, status, errorThrown) {
   /* An error occurred on the server or in the communications */
   // Hide progress indicator
   wait(false);
   $("div.guide-empty")
      .html("<p><b>Villa kom upp</b> í samskiptum við netþjón Greynis</p>")
      .show();
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
   if (wId === undefined) {
      name = $(this).text(); // No associated token: use the contained text
   }
   else {
      // Obtain the name in nominative case from the token
      var ix = parseInt(wId.slice(1));
      var out = $("div#result");
      var tokens = out.data("tokens");
      var wl = tokens[ix];
      if (!wl[2].length) {
         name = wl[1];
      }
      else {
         name = wl[2][0][0];
      }
   }
   queryPerson(name);
   ev.stopPropagation();
}

function showEntity(ev) {
   // Send a query to the server
   queryEntity($(this).text());
   ev.stopPropagation();
}

function makeSourceList(sources) {
   // Return a HTML rendering of a list of articles where the person or entity name appears
   if (!sources) {
      return undefined;
   }
   var $table = $("<table class='table table-hover'>")
      .append($("<thead>")
         .append($("<tr>")
            .append(
               $("<th>").text("Tími"),
               $("<th>").text("Fyrirsögn")
            )
         )
      );
   var $tbody = $table.append($("<tbody>"));
   $.each(sources, function(i, obj) {
      var $tr = $("<tr class='article'>").attr("data-uuid", obj.uuid).append(
         $("<td>").text(obj.ts.replace("T", " ")),
         $("<td class='heading'>").text(obj.heading)
            .prepend($("<img>").attr("src", "/static/sources/" + obj.domain + ".png").attr("width", "16").attr("height", "16"))
      );
      $tbody.append($tr);
   });
   return $table;
}

function makeSearchList(results) {
   // Return a HTML rendering of a list of articles in a search result
   if (!results) {
      return undefined;
   }
   var $table = $("<table class='table table-hover'>")
      .append($("<thead>")
         .append($("<tr>")
            .append(
               $("<th>").text("Tími"),
               $("<th>").text("Fyrirsögn"),
               $("<th class='count'>").text("Líkindi")
            )
         )
      );
   var $tbody = $table.append($("<tbody>"));
   $.each(results, function(i, obj) {
      var $tr = $("<tr class='article'>").attr("data-uuid", obj.uuid)
         .append(
            $("<td class='ts'>").text(obj.ts_text),
            $("<td class='heading'>").text(obj.heading)
               .prepend($("<img>").attr("src", "/static/sources/" + obj.domain + ".png")
                  .attr("width", "16").attr("height", "16")),
            $("<td class='count'>").text(formatReal(obj.similarity, 1) + "%")
         );
      $tbody.append($tr);
   });
   return $table;
}

function imgError(img) {
   // A (person) image failed to load client-side
   $(img).hide();
   // Make sure we only report each broken image once per client session
   if ($(img).data('err')) {
      return;
   }
   // Report broken image to server
   reportImage(img, "broken", function(i) {
      $(img).data('err', true);
      if (i) {
         $(img).show();
      }
   });
}

function reportImage(img, status, successFunc) {
   // Report image status to server
   var q = { 
      name: $(img).attr('title'),
      url: $(img).attr('src'),
      status: status
   };
   $(img).attr('src', '/static/img/placeholder.png');
   serverQuery('/reportimage',
      q,
      function(r) {
         if (r['found_new'] && r['image']) {
            // Server found a new image for us
            $(img).attr('src', r['image'][0]);
            $(img).attr('width', r['image'][1]);
            $(img).attr('height', r['image'][2]);
         }
         if (successFunc) {
            successFunc(r['image']);
         }
      }, // successFunc
      null, // completeFunc
      null // error Func
      );
}

function blacklistImage(img) {
   // User reporting that a person image is wrong
   $("span.imgreport").hide();
   $(img).stop().animate({ opacity: 0 }, function() {
      reportImage(img, "wrong", function(i) {
         if (i) {
            $(img).stop().animate({ opacity: 1.0 });
         } else {
            $(img).hide();
            $("span.imgreport").hide();
         }
      });
   });
}

function displayImage(p, img_info) {
   // Create and show image and associated elements
   var img = $("<img></img>")
            .attr("src", img_info.src)
            .attr("width", img_info.width)
            .attr("height", img_info.height)
            .attr("title", img_info.name)
            .attr("onerror", "imgError(this);");
   p.append(
      $("<a></a>")
      .attr("href", img_info.link)
      .addClass("imglink")
      .html(img)
   )
   .append(
      $("<span></span>")
      .addClass("imgreport")
      .html(
         $("<a>Röng mynd?</a>").click(function(){
            blacklistImage(img);
         })
      )
   );
   $(p.find('a.imglink, span.imgreport')).mouseenter(function () {
      $("span.imgreport").show();
   });
   $(p.find('a.imglink')).mouseleave(function () {
      $("span.imgreport").hide();
   });
}

function populateQueryResult(r) {
   // Display the JSON result of a query sent to the server
   // Hide progress indicator
   wait(false);
   var q = $("<h3 class='query'></h3>");
   q.text(r.q);
   var image_container = $("<p class='image'></p>");
   var answer;
   var searchResult;
   var key = "";
   var articles;

   if (r.valid) {
      // This is a valid query response: present the response items in a bulleted list
      if (r.image !== undefined) {
         // The response contains an image: insert it
         displayImage(image_container, r.image);
      }
      answer = $("<ul></ul>");
      var rlist;
      if (r.qtype === "Word") {
         rlist = r.response.answers;
         if (rlist && rlist.length) {
            var c = r.response.count;
            var g = correctPlural(c, "einni", "grein", "greinum");
            answer = $("<p></p>").text("'" + r.key + "' kemur fyrir í " + g + ", ásamt eftirtöldum orðum:")
               .append($("<ul></ul>"));
         }
      }
      else
      if (r.qtype === "Person" || r.qtype === "Entity") {
         // Title or definition list
         rlist = r.response.answers;
         articles = makeSourceList(r.response.sources);
         key = r.key;
      }
      else
      if (r.qtype !== "Search") {
         rlist = r.response;
      }
      if (r.qtype === "Search" && r.response.answers.length > 0) {
         // Article search by terms
         q = $("<h3 class='query'>");
         $.each(r.response.weights, function(i, t) {
            q.append($("<span></span>").attr("class", "weight" + (t.w * 10).toFixed(0)).text(t.x));
            q.append(" ");
         });
         searchResult = makeSearchList(r.response.answers);
      }
      else
      if (rlist !== undefined && rlist.length === undefined && rlist.answer !== undefined) {
         // We have a single text answer
         answer = $("<p class='query-empty'></p>")
            .html("<span class='green glyphicon glyphicon-play'></span>&nbsp;")
            .append(rlist.answer);
      }
      else
      if (!rlist || !rlist.length) {
         answer = $("<p class='query-empty'></p>")
            .html("<span class='red glyphicon glyphicon-play'></span>&nbsp;Ekkert svar fannst.");
      }
      else {
         $.each(rlist, function(ix, obj) {
            var li;
            if (r.qtype === "Word") {
               if (obj.cat.startsWith("person_")) {
                  li = $("<li>").html($("<span class='name'></span>").text(obj.stem));
               }
               else
               if (obj.cat.startsWith("entity") || obj.cat.startsWith("sérnafn")) {
                  li = $("<li>").html($("<span class='entity'></span>").text(obj.stem));
               }
               else {
                  li = $("<li>").text(obj.stem + " ").append($("<small></small>").text(obj.cat));
               }
            }
            else {
               if (r.qtype === "Title") {
                  // For person names, generate a 'name' span
                  li = $("<li>").html($("<span class='name'></span>").text(obj.answer));
               }
               else {
                  li = $("<li>").text(obj.answer);
               }
               var urlList = obj.sources;
               var artList = li.append($("<span class='art-list'></span>")).children().last();
               for (var i = 0; i < urlList.length; i++) {
                  var u = urlList[i];
                  var img = $("<img width='16' height='16'></img>")
                     .attr("src", "/static/sources/" + u.domain + ".png");
                  var art_link = $("<span class='art-link'></span>")
                     .attr("title", u.heading)
                     .attr("data-uuid", u.uuid)
                     .attr("data-toggle", "tooltip")
                     .html(img);
                  artList.append(art_link);
               }
            }
            answer.append(li);
         });
      }
   }
   else {
      // An error occurred
      answer = $("<p class='query-error'></p>");
      if (r.error === undefined) {
         answer.html("<span class='red glyphicon glyphicon-play'></span>&nbsp;")
            .append("Þetta er ekki fyrirspurn sem Greynir skilur. ")
            .append($("<a></a>").attr("href", "/analysis?txt=" + r.q).text("Smelltu hér til að málgreina."));
      }
      else {
         answer.html("<span class='red glyphicon glyphicon-play'></span>&nbsp;")
            .text(r.error);
      }
   }
   $("div.guide-empty").css("display", "none");
   // Show the original query
   $("div#result-query").css("display", "block").html(q);
   if (searchResult) {
      // Display a search result; hide the person/entity tabs
      $("div#result-tabs").css("display", "none");
      // Display the search results
      $("#search-result-list").html(searchResult);
      $("div#search-result").css("display", "block");
   }
   else {
      // Display person/entity tabs; hide the search result div
      $("div#result-tabs").css("display", "block");
      $("div#search-result").css("display", "none");
      $("div#titles").html(image_container).append(answer);
      if (articles) {
         $("#article-list").html(articles);
         $("#article-key").text(key);
         // Enable the articles tab
         $("#tab-a-articles").attr("data-toggle", "tab");
         $("#tab-li-articles").removeClass("disabled");
      }
      else {
         $("#article-list").html("");
         $("#article-key").text("");
         // Disable the articles tab
         $("#tab-a-articles").attr("data-toggle", "");
         $("#tab-li-articles").addClass("disabled");
      }
      $('#result-hdr a:first').tab('show');
      // A title query yields a list of names
      // Clicking on a name submits a query on it
      $("#entity-body span.name").click(showPerson);
      $("#entity-body span.entity").click(showEntity);
   }
   // Activate bootstrap tooltips for article icons
   $('[data-toggle="tooltip"]').tooltip({ 'animation': false });
   // Click handler for article icons
   $("span.art-link").add("tr.article").click(function(ev) {
      // Show a source article
      wait(true); // This can take time, if a parse is required
      $("#url").attr("placeholder", "Málgreining í gangi...");
      openURL("/page?id=" + $(this).attr("data-uuid"), ev);
   });
}

function clearQueryResult() {
   // Clear previous result
   $("div#result-query").css("display", "none");
   $("div#result-tabs").css("display", "none");
   $("div#search-result").css("display", "none");
   // Display progress indicator
   wait(true);
}

// Actions encoded in URLs
var urlToFunc = {
   "q" : _submitQuery
};

var funcToUrl = {
   _submitQuery : "q"
};

function navToHistory(func, q) {
   if (urlToFunc[func] === undefined) {
      // Invalid function
      return;
   }
   // Navigate to a previous state encoded in a URL
   $("#url").val(q.q); // Go back to original query string
   // Execute the original query function again
   urlToFunc[func](q);
}

function _submitQuery(q) {
   clearQueryResult();
   q.client_type = "www";
   q.client_id = navigator.userAgent;
   // Launch the query
   serverQuery('/query.api',
      q, // Query dictionary
      populateQueryResult, // successFunc
      null, // completeFunc
      handleQueryError // error Func
   );
}

function analyzeQuery(q) {
   // Submit the query in the url input field to the server
   if (queryInProgress) {
      // Already waiting on a query
      return;
   }
   if (q.q.startsWith("http://") || q.q.startsWith("https://")) {
      wait(true); // Show spinner while loading page
      window.location.href = "/page?url=" + encodeURIComponent(q.q);
      return;
   }
   _submitQuery(q);
}

function urlButtonClick() {
   var q = $("#url").val().trim();
   analyzeQuery({ q: q, autouppercase: false });
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

function autoCompleteLookup(q, done)  {
   // Only trigger lookup for certain prefixes
   var none = { 'suggestions': [] };
   var whois = 'hver er ';
   var whatis = 'hvað er ';
   var minqlen = Math.max(whois.length, whatis.length) + 1;
   var valid = (q.toLowerCase().startsWith(whois) || q.toLowerCase().startsWith(whatis)) &&
               q.length >= minqlen && !q.endsWith('?');
   if (!valid) {
      done(none);
      return;
   }
   // Cancel any active request
   if (autoCompleteLookup.req) {
      autoCompleteLookup.req.abort();
   }
   // Local caching
   if (autoCompleteLookup.cache === undefined) {
      autoCompleteLookup.cache = { };
   }
   if (autoCompleteLookup.cache[q] !== undefined) {
      done(autoCompleteLookup.cache[q]);
      return;
   }
   // Ajax request to server
   autoCompleteLookup.req = $.ajax({
      type: 'GET',
      url: "/suggest?q=" + encodeURIComponent(q),
      dataType: "json",
      success: function(json) {
         autoCompleteLookup.cache[q] = json; // Save to local cache
         done(json);
      },
      error: function(ajaxContext) {
         done(none);
      }
   });
}

function initMain(jQuery) {
   // Initialization
   // Set up event handlers
   $("#url")
      .click(function(ev) {
         var start = this.selectionStart;
         var end = this.selectionEnd;
         var len = this.value.length;
         if ((start === 0 && end === 0) || (start === len && end === len)) {
            this.setSelectionRange(0, len);
         }
      })
      .keydown(function(ev) {
         if (ev.which === 13) {
            var q = this.value.trim();
            analyzeQuery({ q: q, autouppercase: false });
            ev.preventDefault();
         }
      })
      .autocomplete({
         lookup: autoCompleteLookup,
         deferRequestBy: 100,
      });

   if (initializeSpeech()) {
      // Speech input seems to be available
      $("#microphone-div").css("display", "block");
      // Make the URL input box smaller to accommodate the microphone
      $("#url-div")
         .removeClass("col-xs-9").removeClass("col-sm-10")
         .addClass("col-xs-7").addClass("col-sm-9");
      // Enable the microphone button to start the speech recognizer
      $("#microphone").click(function(ev) {
         $("#url").val("");
         $("#url")
            .attr("placeholder", "Talaðu í hljóðnemann! Til dæmis: Hver er seðlabankastjóri?");
         $(this)
            .removeClass("btn-success")
            .addClass("btn-danger");
         recognizer.start();
      });
   }
   else {
      $("#url").attr("placeholder", "");
   }

   // Check whether a query was encoded in the URL
   var rqVars = getUrlVars();
   if (rqVars.f !== undefined && rqVars.q !== undefined) {
      // We seem to have a legit query URL
      navToHistory(rqVars.f, { q : rqVars.q });
   }

   // Select all text in the url input field
   $("#url").get(0).setSelectionRange(0, $("#url").val().length);

   // Clicking in italic words in the guide
   $("div.guide-empty i").click(function(ev) {
      openURL("/?f=q&q=" + encodeURIComponent($(this).text()), ev);
   });

   // Activate the top navbar
   $("#navid-main").addClass("active");
}
