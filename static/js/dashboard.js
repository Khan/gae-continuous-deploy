$(function() {

var MAX_SSE_RETRIES = 3;

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
 * @param {boolean} running Whether Mr Deploy is running.
 */
var setStatus = function(running) {
    var status = running ? "I&rsquo;m working!" :
            "I&rsquo;m napping... zed zed zed...";

    $("#status")
        .toggleClass("alert-success", running)
        .toggleClass("alert-error", !running)
        .find(".status-msg")
            .html(status)
    ;

    $("#buttons")
        .find("[data-action='start']").toggleDisabled(running).end()
        .find("[data-action='stop']").toggleDisabled(!running).end()
        .find("[data-action='restart']").toggleDisabled(!running).end()
    ;
};

// TODO(david): Send status updates with the server-sent events stream
var pollStatus = function() {
    $.getJSON("/deploy/status", function(data) {
        setStatus(data.running);
    });
    // TODO(david): Handle server error response
};


/**
 * Set up an SSE stream to get deploy output and status "pushed" from server.
 * @param {number=} retries Optional. Number of times we've retried connecting
 *     to the event stream.
 */
var setupStream = function(retries) {

    // IE does not support Server-Sent Events, but there exist polyfills if for
    // some unfathomable reason we want to support IE (Bill Gates comes again?)
    var source = new EventSource('/deploy/stream');

    source.addEventListener('mr_deploy_output', function(event) {
        var line = $("<div>").text(event.data).html();
        $("#console-text")
            .append(line + "\n")
            .scrollTop($("#console-text")[0].scrollHeight);
    });

    source.addEventListener('mr_deploy_status', function(event) {
        setStatus(JSON.parse(event.data));
    });

    source.addEventListener('error', function(event) {
        if (window.console) {
            console.log('Error in SSE stream:', event);
        }

        // Try to re-establish the connection a few times, but give up and
        // reload page after we've had enough
        retries = _.isNumber(retries) ? retries : 0;
        if (retries > MAX_SSE_RETRIES) {
            window.location.reload();
        } else {
            window.setTimeout(_.bind(setupStream, null, retries + 1), 3000);
        }
    });

};

var init = function() {
    $("#buttons").on("click", ".btn", function(event) {
        $("#buttons .btn").toggleDisabled(true);

        var action = $(event.currentTarget).data("action");
        $.post("/deploy/please/" + action);
    });

    // TODO(david): On resize as well
    $("#console-text")
        .css("height", $(window).height() - 520)
        .scrollTop($("#console-text")[0].scrollHeight);

    pollStatus();
    setupStream();
};

init();

});
