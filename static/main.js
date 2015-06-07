
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
var TOK_UNKNOWN = 15;

var TOK_P_BEGIN = 10001; // Block begin
var TOK_P_END = 10002; // Block end

var TOK_S_BEGIN = 11001; // Sentence begin
var TOK_S_END = 11002; // Sentence end

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

function escapeHtml(string) {
   /* Utility function to properly encode a string into HTML */
   return String(string).replace(/[&<>"'\/]/g, function (s) {
      return entityMap[s];
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
   var wl = tokens[ix];
   var offset = $(this).position();
   var left = Math.min(offset.left, 600);
   var i;

   // Highlight the token
   $(this).addClass("highlight");

   if (wl[0] == TOK_WORD) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Word: list its potential meanings
      for (i = 0; i < wl[2].length; i++) {
         var form = wl[2][i];
         $("div.info").append("<p>" + form[2] + " <b>" + form[0] + "</b> <i>" + form[5] + "</i></p>");
      }
   }
   else
   if (wl[0] == TOK_NUMBER) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the parsed floating-point number to 2 decimal places
      $("div.info").append("<p>" + wl[2][0].toFixed(2) + "</p>");
      // Show cases, if available
      if (wl[2][1] !== null)
         for (i = 0; i < wl[2][1].length; i++)
            $("div.info").append("<p>" + wl[2][1][i] + "</p>");
   }
   else
   if (wl[0] == TOK_PERCENT) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the parsed floating-point number to 1 decimal place
      $("div.info").append("<p>" + wl[2].toFixed(1) + "%</p>");
   }
   else
   if (wl[0] == TOK_ORDINAL) {
      $("div.info").html("<p><b>" + wl[1] + ".</b></p>");
      // Show the parsed number
      $("div.info").append("<p>" + wl[2] + "</p>");
   }
   else
   if (wl[0] == TOK_DATE) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the date in ISO format
      $("div.info").append("<p>" + iso_date(wl[2]) + "</p>");
   }
   else
   if (wl[0] == TOK_CURRENCY) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the ISO code for the currency
      $("div.info").append("<p>" + wl[2][0] + "</p>");
      // Show cases, if available
      if (wl[2][1] !== null)
         for (i = 0; i < wl[2][1].length; i++)
            $("div.info").append("<p>" + wl[2][1][i] + "</p>");
   }
   else
   if (wl[0] == TOK_AMOUNT) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the amount as well as the ISO code for its currency
      $("div.info").append("<p>" + wl[2][0] + " " + wl[2][1].toFixed(2) + "</p>");
      // Show cases, if available
      if (wl[2][2] !== null)
         for (i = 0; i < wl[2][2].length; i++)
            $("div.info").append("<p>" + wl[2][2][i] + "</p>");
   }
   else
   if (wl[0] == TOK_PERSON) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show name and gender
      $("div.info").append("<p>" + wl[2][0] + " " + wl[2][1] + "</p>");
      // Show cases, if available
      if (wl[2][2] !== null)
         for (i = 0; i < wl[2][2].length; i++)
            $("div.info").append("<p>" + wl[2][2][i] + "</p>");
   }
   else
   if (wl[0] == TOK_TIMESTAMP) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the timestamp in ISO format
      $("div.info").append("<p>" + iso_timestamp(wl[2]) + "</p>");
   }
   $("div.info")
      .css("top", offset.top.toString() + "px")
      .css("left", left.toString() + "px")
      .css("visibility", "visible");
}

function hoverOut() {
   // Stop hovering over a word
   $("div.info").css("visibility", "hidden");
   $(this).removeClass("highlight");
}

function populateResult(json) {
   // Display the results of analysis by the server
   // Hide progress indicator
   $("div#wait").css("display", "none");
   // Clear the previous result, if any, and associate the
   // incoming token list with the result DIV
   $("#tok-time").text(json.result.tok_time.toFixed(2));
   $("#parse-time").text(json.result.parse_time.toFixed(2));
   $("#tok-num").text(json.result.tok_num);
   $("#tok-sent").text(json.result.tok_sent);
   $("#tok-info").css("visibility", "visible");
   var out = $("div#result");
   var tokens = json.result.tokens;
   out.data("tokens", tokens);
   var i;
   var s = "";
   var wsp = ""; // Pending whitespace
   for (i = 0; i < tokens.length; i++) {
      var wl = tokens[i];
      if (wl[0] == TOK_PUNCTUATION) {
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
            s += wl[1];
            wsp = "";
         }
      }
      else
      if (wl[0] == TOK_WORD) {
         if (wl[2] === null || wl[2].length == 0)
            // Word not recognized
            s += wsp + "<i class='nf'>" + wl[1] + "</i>";
         else
            s += wsp + "<i id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_P_BEGIN) {
         s += "<p>";
         wsp = "";
      }
      else
      if (wl[0] == TOK_P_END) {
         s += "</p>";
         wsp = "";
      }
      else
      if (wl[0] == TOK_S_BEGIN) {
         var c = "sent";
         if (wl[2] > 0)
            // This sentence has at least one parse tree: mark it
            c += " parsed";
         s += "<span class='" + c + "'>";
         wsp = "";
      }
      else
      if (wl[0] == TOK_S_END) {
         s += "</span>";
         // Keep pending whitespace unchanged
      }
      else
      if (wl[0] == TOK_NUMBER) {
         s += wsp + "<i class='number' id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_PERCENT) {
         s += wsp + "<i class='percent' id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_ORDINAL) {
         s += wsp + "<i class='ordinal' id='w" + i + "'>" + wl[1] + ".</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_DATE) {
         s += wsp + "<i class='date' id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_TIMESTAMP) {
         s += wsp + "<i class='timestamp' id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_CURRENCY) {
         s += wsp + "<i class='currency' id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_AMOUNT) {
         s += wsp + "<i class='amount' id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_PERSON) {
         s += wsp + "<i class='person' id='w" + i + "'>" + wl[1] + "</i>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_YEAR || wl[0] == TOK_TELNO || wl[0] == TOK_TIME) {
         s += wsp + "<b>" + wl[1] + "</b>";
         wsp = " ";
      }
      else
      if (wl[0] == TOK_UNKNOWN) {
         // Token not recognized
         s += wsp + "<i class='nf'>" + wl[1] + "</i>";
         wsp = " ";
      }
   }
   out.html(s);
   // Put a hover handler on each word
   $("div#result i").hover(hoverIn, hoverOut);
}

function analyzeUrl() {
   // Ajax query to the server
   // Clear previous result
   $("div#result").html("");
   // Display progress indicator
   $("div#wait").css("display", "block");
   // Hide the statistics
   $("#tok-info").css("visibility", "hidden");
   // Launch the query
   serverQuery('/analyze',
      { url: $("#url").val().trim() },
      populateResult
   );
}

