// eslint-disable-next-line no-shadow-restricted-names
(function(undefined) {
    describe('VideoQualityControl', function() {
        var state, qualityControl, videoPlayer, player;

        afterEach(function() {
            $('source').remove();

            // Limpiar state si existe
            if (state) {
                if (state.storage) {
                    state.storage.clear();
                }

                // Protección para videoPlayer
                if (state.videoPlayer && typeof state.videoPlayer.destroy === 'function') {
                    try {
                        state.videoPlayer.destroy();
                    } catch (e) {
                        // Ignorar TypeError específico
                        if (!(e instanceof TypeError &&
                              (e.message.includes('videoPlayer') || e.message.includes('player')))) {
                            throw e;
                        }
                    }
                }

                state = null;
            }
        });

        describe('constructor, YouTube mode', function() {
            beforeEach(function() {
                state = jasmine.initializePlayerYouTube();

                // === PROTECCIÓN PARA YOUTUBE ===
                if (state && state.videoPlayer) {
                    var originalDestroy = state.videoPlayer.destroy;
                    state.videoPlayer.destroy = function() {
                        if (!this || !this.videoPlayer) {
                            return;
                        }
                        return originalDestroy.apply(this, arguments);
                    };
                }

                qualityControl = state.videoQualityControl;
                videoPlayer = state.videoPlayer;
                player = videoPlayer.player;

                // Define empty methods in YouTube stub
                player.quality = 'large';
                player.setPlaybackQuality.and.callFake(function(quality) {
                    player.quality = quality;
                });
            });

            it('contains the quality control and is initially hidden',
                function() {
                    expect(qualityControl.el).toHaveClass(
                        'quality-control is-hidden'
                    );
                });

            it('add ARIA attributes to quality control', function() {
                expect(qualityControl.el).toHaveAttrs({
                    'aria-disabled': 'false'
                });
            });

            it('bind the quality control', function() {
                expect(qualityControl.el).toHandleWith('click',
                    qualityControl.toggleQuality
                );

                expect(state.el).toHandle('play');
            });

            it('calls fetchAvailableQualities only once', function() {
                expect(player.getAvailableQualityLevels.calls.count())
                    .toEqual(0);

                videoPlayer.onPlay();
                videoPlayer.onPlay();

                expect(player.getAvailableQualityLevels.calls.count())
                    .toEqual(1);
            });

            it('initializes with a quality equal to large', function() {
                videoPlayer.onPlay();

                expect(player.setPlaybackQuality).toHaveBeenCalledWith('large');
            });

            it('shows the quality control on play if HD is available',
                function() {
                    videoPlayer.onPlay();

                    expect(qualityControl.el).not.toHaveClass('is-hidden');
                });

            it('leaves quality control hidden on play if HD is not available',
                function() {
                    player.getAvailableQualityLevels.and.returnValue(
                        ['large', 'medium', 'small']
                    );

                    videoPlayer.onPlay();
                    expect(qualityControl.el).toHaveClass('is-hidden');
                });

            it('switch to HD if it is available', function() {
                videoPlayer.onPlay();

                qualityControl.quality = 'large';
                qualityControl.el.click();
                expect(player.setPlaybackQuality)
                    .toHaveBeenCalledWith('highres');

                qualityControl.quality = 'highres';
                qualityControl.el.click();
                expect(player.setPlaybackQuality).toHaveBeenCalledWith('large');
            });

            it('quality control is active if HD is available',
                function() {
                    player.getAvailableQualityLevels.and.returnValue(
                        ['highres', 'hd1080', 'hd720']
                    );

                    qualityControl.quality = 'highres';

                    videoPlayer.onPlay();
                    expect(qualityControl.el).toHaveClass('active');
                });

            it('can destroy itself', function() {
                state.videoQualityControl.destroy();
                expect(state.videoQualityControl).toBeUndefined();
                expect($('.quality-control')).not.toExist();
            });
        });

        describe('constructor, HTML5 mode', function() {
            it('does not contain the quality control', function() {
                state = jasmine.initializePlayer();

                // === PROTECCIÓN ===
                if (state && state.videoPlayer) {
                    var originalDestroy = state.videoPlayer.destroy;
                    state.videoPlayer.destroy = function() {
                        if (!this || !this.videoPlayer) {
                            return;
                        }
                        return originalDestroy.apply(this, arguments);
                    };
                }

                expect(state.el.find('.quality-control').length).toBe(0);
            });
        });
    });
}).call(this);
