// eslint-disable-next-line no-shadow-restricted-names
(function(undefined) {
    describe('Video', function() {
        var state;

        afterEach(function() {
            $('source').remove();
            window.VideoState = {};
            window.VideoState.id = {};
            window.YT = jasmine.YT;

            if (state) {
                if (state.storage) {
                    state.storage.clear();
                }

                if (state.videoPlayer && typeof state.videoPlayer.destroy === 'function') {
                    try {
                        state.videoPlayer.destroy();
                    } catch (e) {
                    }
                }

                state = null;
            }
        });

        describe('constructor', function() {
            describe('YT', function() {
                var state;

                beforeEach(function() {
                    loadFixtures('video.html');
                    $.cookie.and.returnValue('0.50');
                });

                describe('by default', function() {
                    beforeEach(function() {
                        state = jasmine.initializePlayerYouTube('video_html5.html');

                        var originalDestroy = state.videoPlayer.destroy;
                        state.videoPlayer.destroy = function() {
                            if (!this.videoPlayer) {
                                return;
                            }
                            return originalDestroy.apply(this, arguments);
                        };
                    });

                    afterEach(function() {
                        if (state) {
                            state.storage.clear();
                            if (state.videoPlayer) {
                                state.videoPlayer.destroy();
                            }
                        }
                    });

                    it('check videoType', function() {
                        expect(state.videoType).toEqual('youtube');
                    });

                    it('set the elements', function() {
                        expect(state.el).toEqual($('#video_id'));
                    });

                    it('parse the videos', function() {
                        expect(state.videos).toEqual({
                            '0.50': '7tqY6eQzVhE',
                            '1.0': 'cogebirgzzM',
                            '1.50': 'abcdefghijkl'
                        });
                    });

                    it('parse available video speeds', function() {
                        expect(state.speeds).toEqual(['0.50', '1.0', '1.50']);
                    });

                    it('set current video speed via cookie', function() {
                        expect(state.speed).toEqual('1.50');
                    });
                });
            });

            describe('HTML5', function() {
                var state;

                beforeEach(function() {
                    $.cookie.and.returnValue('0.75');
                    state = jasmine.initializePlayer('video_html5.html');
                });

                afterEach(function() {
                    if (state) {
                        state.storage.clear();
                        if (state.videoPlayer) {
                            state.videoPlayer.destroy();
                        }
                    }
                });

                describe('by default', function() {
                    it('check videoType', function() {
                        expect(state.videoType).toEqual('html5');
                    });

                    it('set the elements', function() {
                        expect(state.el).toEqual($('#video_id'));
                    });

                    it('doesn\'t have `videos` dictionary', function() {
                        expect(state.videos).toBeUndefined();
                    });

                    it('parse available video speeds', function() {
                        var speeds = jasmine.stubbedHtml5Speeds;
                        expect(state.speeds).toEqual(speeds);
                    });

                    it('set current video speed via cookie', function() {
                        expect(state.speed).toEqual(1.5);
                    });
                });

                describe('HTML5 API is available', function() {
                    it('create the Video Player', function() {
                        expect(state.videoPlayer.player).not.toBeUndefined();
                    });
                });
            });
        });

        describe('YouTube API is not loaded', function() {
            var state;

            beforeEach(function() {
                window.YT = undefined;
                state = jasmine.initializePlayerYouTube();

                var originalDestroy = state.videoPlayer.destroy;
                state.videoPlayer.destroy = function() {
                    if (!this || !this.videoPlayer) {
                        return;
                    }
                    return originalDestroy.apply(this, arguments);
                };

                if (state.el && state.el.length) {
                    state.el.off('remove');
                }
            });

            afterEach(function(done) {
                if (state) {
                    state.storage.clear();

                    var videoPlayer = state.videoPlayer;
                    var el = state.el;

                    if (videoPlayer && typeof videoPlayer.destroy === 'function') {
                        try {
                            videoPlayer.destroy();
                        } catch (e) {
                        }
                    }

                    if (el && el.length) {
                        el.remove();
                    }

                    state = null;
                }

                setTimeout(done, 50);
            });

            xit('callback, to be called after YouTube API loads, exists and is called', function(done) {
                window.YT = jasmine.YT;
                window.onYouTubeIframeAPIReady();

                jasmine.waitUntil(function() {
                    return state && state.youtubeApiAvailable === true;
                }).done(function() {
                    expect(window.onYouTubeIframeAPIReady).not.toBeUndefined();
                }).always(done);
            });
        });

        describe('checking start and end times', function() {
            var state;  // State específico para este grupo
            var miniTestSuite = [
                {
                    itDescription: 'both times are proper',
                    data: {start: 12, end: 24},
                    expectData: {start: 12, end: 24}
                },
                {
                    itDescription: 'start time is invalid',
                    data: {start: '', end: 24},
                    expectData: {start: 0, end: 24}
                },
                {
                    itDescription: 'end time is invalid',
                    data: {start: 12, end: ''},
                    expectData: {start: 12, end: null}
                },
                {
                    itDescription: 'start time is less than 0',
                    data: {start: -12, end: 24},
                    expectData: {start: 0, end: 24}
                },
                {
                    itDescription: 'start time is greater than end time',
                    data: {start: 42, end: 24},
                    expectData: {start: 42, end: null}
                }
            ];

            afterEach(function() {
                if (state) {
                    state.storage.clear();
                    if (state.videoPlayer) {
                        state.videoPlayer.destroy();
                    }
                }
            });

            $.each(miniTestSuite, function(index, test) {
                itFabrique(test.itDescription, test.data, test.expectData);
            });

            function itFabrique(itDescription, data, expectData) {
                it(itDescription, function() {
                    state = jasmine.initializePlayer('video.html', {
                        start: data.start,
                        end: data.end
                    });

                    if (state && state.videoPlayer) {
                        var originalDestroy = state.videoPlayer.destroy;
                        state.videoPlayer.destroy = function() {
                            if (!this.videoPlayer) {
                                return;
                            }
                            return originalDestroy.apply(this, arguments);
                        };
                    }

                    expect(state.config.startTime).toBe(expectData.start);
                    expect(state.config.endTime).toBe(expectData.end);
                });
            }
        });

        // Disabled 11/25/13 due to flakiness in master
        xdescribe('multiple YT on page', function() {
            var state1, state2, state3;

            beforeEach(function() {
                loadFixtures('video_yt_multiple.html');

                spyOn($, 'ajaxWithPrefix');

                $.ajax.calls.length = 0;
                $.ajaxWithPrefix.calls.length = 0;

                Video.clearYoutubeXhr();

                state1 = new Video('#example1');
                state2 = new Video('#example2');
                state3 = new Video('#example3');
            });

            it('check for YT availability is performed only once', function() {
                var numAjaxCalls = 0;

                numAjaxCalls = $.ajax.calls.length;
                numAjaxCalls -= $.ajaxWithPrefix.calls.length;
                numAjaxCalls -= 3;
                numAjaxCalls -= 3;

                expect(numAjaxCalls).toBe(1);
            });
        });
    });
}).call(this);
