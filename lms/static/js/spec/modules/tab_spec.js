describe('Tab', function() {
  beforeEach(function() {
    loadFixtures('coffee/fixtures/tab.html');
    this.items = JSON.parse(readFixtures('coffee/fixtures/items.json'));
  });

  describe('constructor', function() {
    beforeEach(function() {
      spyOn($.fn, 'tabs');
      this.tab = new Tab(1, this.items);
    });

    it('set the element', function() {
      expect(this.tab.el).toEqual($('#tab_1'));
    });

    it('build the tabs', function() {
      const links = $('.navigation li>a').map(function() { return $(this).attr('href'); }).get();
      expect(links).toEqual(['#tab-1-0', '#tab-1-1', '#tab-1-2']);
  });

    it('build the container', function() {
      const containers = $('section').map(function() { return $(this).attr('id'); }).get();
      expect(containers).toEqual(['tab-1-0', 'tab-1-1', 'tab-1-2']);
  });

    it('bind the tabs', function() {
      expect($.fn.tabs).toHaveBeenCalledWith({activate: this.tab.onShow});
    });
  });

  // jQuery UI 1.10+ renamed the show event to activate.
  // http://jqueryui.com/upgrade-guide/1.9/#deprecated-show-event-renamed-to-activate
  // The ui object for activate provides ui.newPanel (the activated panel element)
  // and ui.newTab (the activated tab anchor element).
  describe('onShow', function() {
    beforeEach(function() {
      this.tab = new Tab(1, this.items);
      this.tab.onShow(null, {newPanel: $('#tab-1-0')});
    });

    it('replace content in the container', function() {
      this.tab.onShow(null, {newPanel: $('#tab-1-1')});
      expect($('#tab-1-0').html()).toEqual('');
      expect($('#tab-1-1').html()).toEqual('Video 2');
      expect($('#tab-1-2').html()).toEqual('');
    });

    it('trigger contentChanged event on the element', function() {
      spyOnEvent(this.tab.el, 'contentChanged');
      this.tab.onShow(null, {newPanel: $('#tab-1-1')});
      expect('contentChanged').toHaveBeenTriggeredOn(this.tab.el);
    });
  });
});
