
/*

   Analyzer.js

   Reynir word category analyzer client script

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

function serverPost(url, parameters) {
   /* Post to the provided URL with the specified parameters */
   var form = $('<form method="post"></form>');
   form.attr("action", url);
   form.attr("target", "_blank"); // Display in new window
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

var ordfl = {
   "no" : "nafnorð",
   "so" : "sagnorð",
   "lo" : "lýsingarorð",
   "ao" : "atviksorð",
   "eo" : "atviksorð",
   "fs" : "forsetning",
   "fn" : "fornafn",
   "pfn" : "persónufornafn",
   "abfn" : "afturbeygt fornafn",
   "to" : "töluorð",
   "töl" : "töluorð",
   "st" : "samtenging",
   "nhm" : "nafnháttarmerki",
   "tala" : "tala",
   "ártal" : "ártal"
};

var descr = {
   "p1" : "fyrsta persóna",
   "p2" : "önnur persóna",
   "p3" : "þriðja persóna",
   "nf" : "nefnifall",
   "þf" : "þolfall",
   "þgf" : "þágufall",
   "ef" : "eignarfall",
   "et" : "eintala",
   "ft" : "fleirtala",
   "kk" : "karlkyn",
   "kvk" : "kvenkyn",
   "hk" : "hvorugkyn",
   "nh" : "nafnháttur",
   "bh" : "boðháttur",
   "vh" : "viðtengingarháttur",
   "fh" : "framsöguháttur",
   "lhþt" : "lýsingarháttur þátíðar",
   "sagnb" : "sagnbót",
   "gm" : "germynd",
   "mm" : "miðmynd",
   "mst" : "miðstig"
};

var nounDescr = {
   "kk" : "karlkyn",
   "kvk" : "kvenkyn",
   "hk" : "hvorugkyn"
};

var caseDescr = {
   "nf" : "nefnifalli",
   "þf" : "þolfalli",
   "þgf" : "þágufalli",
   "ef" : "eignarfalli"
};

var addDescr = {
   "no" : { "gr" : "með greini" },
   "so" : {
      "NT" : "nútíð",
      "ÞT" : "þátíð",
      "MM" : "miðmynd",
      "GM" : "germynd",
      "VH" : "viðtengingarháttur",
      "FH" : "framsöguháttur",
      "BH" : "boðháttur"
   }
};

function wordMeaning(wl) {
   // Create the HTML that is displayed in a pop-up balloon for a word
   // Dissect the terminal name
   var tname = wl[3];
   var meanings = wl[2];
   var parts = (tname === undefined) ? [] : tname.split("_");
   var category = wl[4];
   var stem = (meanings.length > 0) ? meanings[0][0] : wl[1];
   var str = "<p class='stem'>" + stem + "</p>";
   var comment = "";
   var i;
   if (category == "no") {
      // For nouns, add the gender to the stem
      for (var gender in nounDescr)
         if (nounDescr.hasOwnProperty(gender) && parts.indexOf(gender) != -1) {
            comment = ", " + nounDescr[gender];
            // Remove the gender from the parts list to avoid duplication
            parts[parts.indexOf(gender)] = null;
            break;
         }
   }
   str += "<p><b>" + ordfl[category] + comment + "</b></p>";
   if (category == "fs") {
      // For pronouns, add the controlled case separately
      var control = "";
      for (var cs in caseDescr)
         if (caseDescr.hasOwnProperty(cs) && parts.indexOf(cs) != -1) {
            control = "stýrir " + caseDescr[cs];
            // Remove the case from the parts list to avoid duplication
            parts[parts.indexOf(cs)] = null;
            break;
         }
      str += "<p class='control'>" + control + "</p>";
   }
   else
   if (category == "so") {
      // For verbs that control case(s), add them separately
      var ix = parts.indexOf("1");
      if (ix == -1)
         ix = parts.indexOf("2");
      if (ix != -1) {
         var control = "";
         for (i = ix + 1; i < parts.length; i++) {
            var cs = parts[i];
            if (cs !== null && caseDescr[cs] !== undefined) {
               // This is a case controlled by a verb
               if (!control.length)
                  control = "stýrir " + caseDescr[cs];
               else
                  control += " og " + caseDescr[cs];
               // Remove the case from the parts list to avoid duplication
               parts[i] = null;
            }
         }
         str += "<p class='control'>" + control + "</p>";
      }
   }
   var d = "";
   for (i = 1; i < parts.length; i++)
      if (parts[i] !== null) {
         var s = descr[parts[i]];
         if (s !== undefined)
            d += d.length ? ", " + s : s;
      }
   // Look up potential additional features from the BIN meanings
   var addLookup = addDescr[category];
   if (addLookup !== undefined) {
      var allMeaningsContain = function(f) {
         var found = true;
         for (var i = 0; i < meanings.length; i++) {
            var form = meanings[i];
            if (form[5].indexOf(f) == -1) {
               found = false;
               break;
            }
         }
         return found;
      };
      for (var f in addLookup) {
         // Loop through all relevant features for this category
         if (allMeaningsContain(f)) {
            // The feature is present in all possible meanings
            if (f != "ÞT" || !allMeaningsContain("LHÞT")) {
               // Take care not to add ÞT if LHÞT is already there
               var s = addLookup[f];
               d += d.length ? ", " + s : s;
            }
         }
      }
   }
   str += "<p>" + d + "</p>";
   if (category != "no" && category != "lo" && category != "fs" &&
      category != "ao" && category != "eo" && category != "st" &&
      category != "töl" && category != "to" &&
      category != "fn" && category != "pfn" && category != "nhm") {
      if (parts.length > 1)
         str += "<p>" + parts.slice(1).join(" ") + "</p>";
      // Word: list its potential meanings
      for (i = 0; i < meanings.length; i++) {
         var form = meanings[i];
         str += "<p>" + form[2] + " <b>" + form[0] + "</b> <i>" + form[5] + "</i></p>";
      }
   }
   return str;
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
   var offset = $(this).offset();
   var i;
   var gender;

   // Highlight the token
   $(this).addClass("highlight");

   if (wl[0] == TOK_WORD) {
      $("div.info").html(wordMeaning(wl));
   }
   else
   if (wl[0] == TOK_NUMBER) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the parsed floating-point number to 2 decimal places
      gender = (wl[2][2] !== null) ? (" " + wl[2][2]) : "";
      $("div.info").append("<p>" + wl[2][0].toFixed(2) + gender + "</p>");
      // Show cases, if available
      if (wl[2][1] !== null)
         for (i = 0; i < wl[2][1].length; i++)
            $("div.info").append("<p>" + wl[2][1][i] + "</p>");
   }
   else
   if (wl[0] == TOK_PERCENT) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the parsed floating-point number to 1 decimal place
      gender = (wl[2][2] !== null) ? (" " + wl[2][2]) : "";
      $("div.info").append("<p>" + wl[2][0].toFixed(1) + "% " + gender + "</p>");
      // Show cases, if available
      if (wl[2][1] !== null)
         for (i = 0; i < wl[2][1].length; i++)
            $("div.info").append("<p>" + wl[2][1][i] + "</p>");
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
      gender = (wl[2][3] !== null) ? (" " + wl[2][3]) : "";
      $("div.info").append("<p>" + wl[2][1] + " " + wl[2][0].toFixed(2) + gender + "</p>");
      // Show cases, if available
      if (wl[2][2] !== null)
         for (i = 0; i < wl[2][2].length; i++)
            $("div.info").append("<p>" + wl[2][2][i] + "</p>");
   }
   else
   if (wl[0] == TOK_PERSON) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      for (i = 0; i < wl[2].length; i++) {
         // Show name, gender and case
         var p = wl[2][i];
         $("div.info").append("<p>" + p[0] + " " + p[1] + " " + p[2] + "</p>");
      }
   }
   else
   if (wl[0] == TOK_TIMESTAMP) {
      $("div.info").html("<p><b>" + wl[1] + "</b></p>");
      // Show the timestamp in ISO format
      $("div.info").append("<p>" + iso_timestamp(wl[2]) + "</p>");
   }
   $("div.info")
      .css("top", offset.top.toString() + "px")
      .css("left", offset.left.toString() + "px")
      .css("visibility", "visible");
}

function hoverOut() {
   // Stop hovering over a word
   $("div.info").css("visibility", "hidden");
   $(this).removeClass("highlight");
}

function add_w(cls, i, wrd) {
   // Add HTML for a single word to s
   return "<i class='" + cls + "' id='w" + i + "'>" + wrd + "</i>";
}

function populateResult(json) {
   // Display the results of analysis by the server
   // Hide progress indicator
   $("div#wait").css("display", "none");

   // Clear the previous result, if any, and associate the
   // incoming token list with the result DIV

   var out = $("div#result");
   var tokens = json.result.tokens;
   out.data("tokens", tokens);
   var i;
   var s = "";
   for (i = 0; i < tokens.length; i++) {
      var wl = tokens[i];
      var wl0 = wl[0];
      if (wl0 & TOK_ERROR_FLAG) {
         // The token has earlier been marked as an error token:
         // enclose it within a span identifying it as such
         wl0 &= ~TOK_ERROR_FLAG;
         s += "<span class='errtok'>";
      }
      if (wl0 == TOK_PUNCTUATION) {
         s += "<i class='p'>" + wl[1] + "</i>";
      }
      else
      if (wl0 == TOK_WORD) {
         if (wl[2] === null || wl[2].length == 0)
            // Word not recognized
            s += "<i class='nf'>" + wl[1] + "</i>";
         else {
            s += "<i class='" + wl[4] + "' id='w" + i + "'>" + wl[1] + "</i>";
         }
      }
      else
      if (wl0 == TOK_P_BEGIN) {
         s += "<p>";
      }
      else
      if (wl0 == TOK_P_END) {
         s += "</p>";
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
         s += "<span class='" + c + "'>";
      }
      else
      if (wl0 == TOK_S_END) {
         s += "</span>";
         // Keep pending whitespace unchanged
      }
      else
      if (wl0 == TOK_NUMBER) {
         s += add_w("number", i, wl[1]);
      }
      else
      if (wl0 == TOK_PERCENT) {
         s += add_w("percent", i, wl[1]);
      }
      else
      if (wl0 == TOK_ORDINAL) {
         s += add_w("ordinal", i, wl[1] + ".");
      }
      else
      if (wl0 == TOK_DATE) {
         s += add_w("date", i, wl[1]);
      }
      else
      if (wl0 == TOK_TIMESTAMP) {
         s += add_w("timestamp", i, wl[1]);
      }
      else
      if (wl0 == TOK_CURRENCY) {
         s += add_w("currency", i, wl[1]);
      }
      else
      if (wl0 == TOK_AMOUNT) {
         s += add_w("amount", i, wl[1]);
      }
      else
      if (wl0 == TOK_PERSON) {
         s += add_w("person", i, wl[1]);
      }
      else
      if (wl0 == TOK_YEAR || wl0 == TOK_TELNO || wl0 == TOK_TIME) {
         s += "<i class='year'>" + wl[1] + "</i>";
      }
      else
      if (wl0 == TOK_UNKNOWN) {
         // Token not recognized
         s += "<i class='nf'>" + wl[1] + "</i>";
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
}

function analyzeTxt() {
   // Ajax query to the server
   // Clear previous result
   $("div#result").html("");
   // Display progress indicator
   $("div#wait").css("display", "block");
   // Launch the query
   serverQuery('/analyze',
      { txt: $("#txt").val().trim() },
      populateResult
   );
}

