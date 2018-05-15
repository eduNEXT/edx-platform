/* Javascript for StudioView. */
(function(define) {
    'use strict';
    define(['jquery'],

        function($) {

            var xblock = $(".xblock-student_view-vertical");
            $(".hidden-rocket-chat").hide()

            $(window).load(function() {

                $( "div.discussion-module" ).replaceWith( xblock);
                $(".loading-animation").hide()

                var targetNode = $(".teams-content")[0];

                // Options for the observer (which mutations to observe)
                var config = {subtree : true, attributes: true}

                // Callback function to execute when mutations are observed
                function fnHandler () {
                    if($("div.discussion-module")[0]){
                        $( "div.discussion-module" ).replaceWith( xblock);
                        $(".loading-animation").hide()
                    }
                }
                // Create an observer instance linked to the callback function
                var observer = new MutationObserver(fnHandler);

                // Start observing the target node for configured mutations
                observer.observe(targetNode, config);

            });

        });
}).call(this, define || RequireJS.define);
