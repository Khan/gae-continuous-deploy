$(function() {

var POLL_STATUS_INTERVAL_MS = 3000;

$.fn.toggleDisabled = function(disable) {
    return this.each(function() {
        var $this = $(this);
        if (disable === undefined) {
            $this.prop("disabled", !$this.prop("disabled"));
        } else {
            $this.prop("disabled", disable);
        }
    });
};

/**
 * Sets Mr Deploy's status.
 * @param {boolean} working Whether Mr Deploy is working.
 */
var setStatus = function(working) {
    var status = working ? "I&rsquo;m working!" :
            "I&rsquo;m napping... zed zed zed...";

    $("#status")
        .toggleClass("alert-success", working)
        .toggleClass("alert-error", !working)
        .find(".status-msg")
            .html(status)
    ;

    $("#buttons")
        .find("[data-action='start']").toggleDisabled(working).end()
        .find("[data-action='stop']").toggleDisabled(!working).end()
        .find("[data-action='restart']").toggleDisabled(!working).end()
    ;
};

var setStatusFromData = function(data) {
    setStatus(data.running);
};

// TODO(david): Send status updates with the server-sent events stream
var pollStatus = function() {
    $.getJSON("/deploy/status", setStatusFromData);
    // TODO(david): Handle server error response
};


function setupStream() {
    // IE does not support Server-Sent Events, but there exist polyfills if for
    // some unfathomable reason we want to support IE (Bill Gates comes again?)
    var source = new EventSource('/deploy/stream');
    source.onmessage = function(e) {
        $("#console-text")
            .append(e.data + "\n")
            .scrollTop($("#console-text")[0].scrollHeight);
    };
}

var init = function() {
    $("#buttons").on("click", ".btn", function(event) {
        $("#buttons .btn").toggleDisabled(true);

        var action = $(event.currentTarget).data("action");
        // TODO(david): Make the server wait for status to be updated, so we can
        //     use the data we get back from the POST instead of another request
        $.post("/deploy/please/" + action, pollStatus);
    });

    // TODO(david): On resize as well
    $("#console-text")
        .css("height", $(window).height() - 520)
        .scrollTop($("#console-text")[0].scrollHeight);

    pollStatus();
    setInterval(pollStatus, POLL_STATUS_INTERVAL_MS);
    setupStream();
};

init();

});
