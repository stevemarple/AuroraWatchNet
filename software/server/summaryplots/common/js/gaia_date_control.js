/* A object-oriented date/time control. User creates a control object
 * then requests information from it, eg the HTML elements to insert
 * into the page (using DOM methods).
 *
 * Features:
 * user-definable earliest/latest date limits
 * configurable inital date
 * increment button to advance/retard date/time by user-definable quantity
 * legal to have multiple controls for the same task
 * does not require ID attributes to be set
 * does not require elements to be inside a form
 * user-definable as to whether UTC or local timezone is used
 * year input can be from a "select" menu or text "input" box
 *
 * Depends on:
 *   strftime(): use gaia_strftime.js or any other strftime function.
 *   gaia_date.js: Needs gaiaDate.isValid(), gaiaDate.isLeapYear() and
 *   other functions in gaia_datejs.
 *
 *
 */


// If a sprintf function exists then import it, else use the one
// from gaiaSprintf
if (!gaiaDate.sprintf)
  if (window.sprintf)
    gaiaDate.sprintf = window.sprintf;
  else
    gaiaDate.sprintf = gaiaSprintf.sprintf;

gaiaDate.dateControl = function (obj) {
  // Should the control work in UTC mode?
  
  if (obj.utc != null) 
    this.utc = (obj.utc == true);
  else
    this.utc = true;
  
  // create default earliest/latest values
  if (this.utc) {
    this.earliestDate = new Date(Date.UTC(1980, 0 ,1));
    this.latestDate = gaiaDate.getUTCStartOfDay(new Date);
  }
  else {
    this.earliestDate = new Date(1980, 0 ,1);
    this.latestDate = gaiaDate.getStartOfDay(new Date);
  }
  
  if (obj.earliestDate)
    this.earliestDate = new Date(obj.earliestDate);

  if (obj.latestDate)
    this.latestDate = new Date(obj.latestDate);

  if (this.earliestDate.valueOf() >= this.latestDate.valueOf()) {
    gaia.log("earliestDate must be before latestDate");
    return false;
  }

  // Initial date setting
  if (obj.date)
    // take a copy so caller cannot ammend our version
    this.date = new Date(obj.date);
  else
    // Take copy - don't alter earliest date as actual date is changed!
    this.date = new Date(this.earliestDate);
  
  if (obj.document)
    this.document = obj.document;
  else
    this.document = window.document;

  this.disabled = (obj.disabled == true);

  // Function to be called when date is changed
  this.userCallback = obj.callback;

  // Allow for control to be updated immediately or for a 'Go' button
  // to activate the callback
  if (obj.immediateUpdate != null)
    this.immediateUpdate = (obj.immediateUpdate == true);
  else
    this.immediateUpdate = true;

  // Need a list of the elements so that when the date is changed the
  // HTML elements can be updated. We need to take care about cyclic
  // reference which will prevent garbage collection when the elements
  // are no longer required. The cyclic references to be concerned
  // about look something like this:
  //
  // dateControl object -> HTMLElement -> callbackFunction ->
  // dateControl object
  //
  // We can breka the cyclic dependency by hooking into the window's
  // unload event. Users could also call the destructor manually.
  //
  // Another area of concern is cyclic dependencies which look like:
  //
  // HTMLElement -> callbackFunction -> HTMLElement
  //
  // This cycle is harder to break, but we are safe since the callback
  // closures don't store a reference to ths HTMLElement but take
  // advantage of the "this" pointer.
  this.elements = new Array;


  // Register a handler to be called with the page is unloaded; by
  // deleting references to the HTMLElements there should be no
  // possiblity of cyclic references interfering with the garbage
  // collection. Once the handler has run we need to remove it, which
  // means keeping a reference to the handler's function closure. That
  // introduces a cyclic dependency which looks like this:
  //
  // HTMLElement -> unload handler -> HTMLElement
  //
  // This means we also need to break this cyclic dependency!
  var t = this;
  if (window.addEventListener) {
    this.eventListener = function () { t.destructor(); return true; };
    window.addEventListener('unload', this.eventListener, true);
  }
  else 
    if (window.attachEvent) {
      this.attachEventFunc = function () { t.destructor(); return true; }
      window.attachEvent('onunload', this.attachEventFunc);
    }
};


gaiaDate.dateControl.prototype.destructor = function ( ) {
  // Remove the references to the HTMLElements
  if (this.elements)
    for (i = 0; i < this.elements.length; ++i) {
      // Remove the references to the element's callbacks
      this.elements[i].onchange = null;
      this.elements[i].onclick = null;
      // Remove out reference to the HTMLElement
      this.elements[i] = null;
    }
  this.elements = null;

  // remove user callback as it may form cyclic references
  this.userCallback = null;

  // Remove any events we created!
  if (this.eventListener) {
    window.removeEventListener('unload', this.eventListener, true);
    this.eventListener = null; // break cyclic dependency
  }

  if (this.attachEventFunc) {
    window.detachEvent('onunload', this.attachEventFunc);
    this.attachEventFunc = null; // break cyclic dependency
  }

  //window.alert('destructor called');
  //window.console.log('destructor called');
  //window.open('destructor=called');
  // this.document.defaultView.open('destructor=called');
  return true;
};


gaiaDate.dateControl.prototype.toString = function () {
  if (this.utc)
    return this.date.toUTCString();
  else
    return this.date.toString();
};


gaiaDate.dateControl.prototype.getDisabled = function () {
  return (this.disabled == true);
};


gaiaDate.dateControl.prototype.setDisabled = function (a) {
  this.disabled = (a == true);
  for (var i = 0; i < this.elements.length; ++i)
    this.elements[i].disabled = this.disabled;
  return this.disabled;
};


// Return a copy of the date (a copy so that the caller cannot ammend
// our date)
gaiaDate.dateControl.prototype.getDate = function ( ) {
  return new Date(this.date);
};


gaiaDate.dateControl.prototype.getEarliestDate = function ( ) {
  return new Date(this.earliestDate);
};


gaiaDate.dateControl.prototype.getLatestDate = function ( ) {
  return new Date(this.latestDate);
};

// User can indicate if user callback should be activated is date is
// changed. Default is to use immediateUpdate setting.
gaiaDate.dateControl.prototype.setEarliestDate = function (d, doCallback) {
  // check it is a date and is before the latest date
  if (!d || d.constructor != Date 
      || d.valueOf() >= this.latestDate.valueOf())
    return false;
  var r = new Date(this.earliestDate);
  this.earliestDate = new Date(d);
  if (this.earliestDate > this.date)
    this.setDate(this.earliestDate, doCallback);
  
  for (var i = 0; i < this.elements.length; ++i) 
    if (this.elements[i].gaiaDateControl.type == 'year')
       this.yearControlCreateOptions(this.elements[i]);
  return r;
};


// User can indicate if user callback should be activated is date is
// changed. Default is to use immediateUpdate setting.
gaiaDate.dateControl.prototype.setLatestDate = function (d, doCallback) {
  // check it is a date and is after the earliest date
  if (!d || d.constructor != Date 
      || d.valueOf() <= this.earliestDate.valueOf())
    return false;

  var r = new Date(this.latestDate);
  this.latestDate = new Date(d);
  if (this.latestDate < this.date)
    this.setDate(this.latestDate, doCallback);

  for (var i = 0; i < this.elements.length; ++i) 
    if (this.elements[i].gaiaDateControl.type == 'year')
      this.yearControlCreateOptions(this.elements[i]);
  return r;
};


// User can indicate if user callback should be activated. Default is
// to use immediateUpdate setting.
gaiaDate.dateControl.prototype.setDate = function (d, doCallback) {
  var r = new Date(this.date);
  if (doCallback === null || doCallback == void 0)
    doCallback = this.immediateUpdate;
  this.date = new Date(d);
  if (this.date.valueOf() < this.earliestDate.valueOf())
    this.date = new Date(this.earliestDate);
  else
    if (this.date.valueOf() > this.latestDate.valueOf())
      this.date = new Date(this.latestDate);
 
  this.refreshControls();
  
  if (doCallback == true && this.userCallback) {
    // Do the user's callback
    if (typeof this.userCallback == "function")
      return this.userCallback(this);
    if (typeof this.userCallback == "string")
      return eval(this.userCallback);
  }
  
  return r;
};


gaiaDate.dateControl.prototype.getImmediateUpdate = function ( ) {
  return this.immediateUpdate;
};


gaiaDate.dateControl.prototype.setImmediateUpdate = function (s) {
  var r = this.immediateUpdate;
  this.immediateUpdate = (s == true);
  return r;
};


gaiaDate.dateControl.prototype.setCallback = function (f) {
  var r = this.userCallback;
  this.userCallback = f;
  return r;
};

// elem: the HTMLElement which intiated the callback
// v: the increment value (increment buttons only)
// doSetDate: set the date value now? (increment buttons only, and
// only when this.immediateUpdate is false)
gaiaDate.dateControl.prototype.callback = function(elem, v, doSetDate) {
  // Get the element's value
  var val;
  switch (elem.tagName.toLowerCase()) {
  case "button":
    val = v;
    break;

  case "input":
    val = elem.value;
    break;
      
  case "select":
    val = elem.options[elem.selectedIndex].value
      break;

  default:
    gaia.log("gaiaDate.dateControl.callback(): Unsupported element type: "
	     + elem.tagName);
    break;
  }
  
  var type = elem.gaiaDateControl.type;
  var d = new Date(this.date);
  
  var daysInYear = 365; 
  if (this.utc) {
    switch (type) {
      case 'year':
	d.setUTCFullYear(parseInt(val)); // might be from input element
      break;

      case 'month':
      d.setUTCMonth(val);
      break;
      
      case 'dom':
      d.setUTCDate(val);
      break;

    case 'doy':
      val = parseInt(val); // from input box
	if (this.date.isUTCLeapYear()) // requires gaia_date.js
	  daysInYear = 366;
	if (val < 1)	
	  val = 1;
	if (val > daysInYear)
	  val = daysInYear;
	if (isFinite(val))
	  d.setUTCDayOfYear(val); // requires gaia_date.js
      break;
      
      case 'hour':
      d.setUTCHours(val);
      break;
      
      case 'minute':
      d.setUTCMinutes(val);
      break;
      
      case 'second':
      d.setUTCSeconds(val);
      break;
      
    case 'increment':
	d.setTime(d.getTime() + parseInt(val));
      break;

    case 'submit':
      break;

      default:
      gaia.log("gaiaDate.dateControl.callback(): Unknown control element: "
	       + type);
      break;
    }
  }
  else {
    switch (type) {
      case 'year':
      d.setFullYear(parseInt(val)); // might be from input element
      break;

      case 'month':
      d.setMonth(val);
      break;
      
      case 'dom':
      d.setDate(val);
      break;

      case 'doy':
      val = parseInt(val); // from input box
	if (this.date.isLeapYear()) // requires gaia_date.js
	  daysInYear = 366;
	if (val < 1)	
	  val = 1;
	if (val > daysInYear)
	  val = daysInYear;
	if (isFinite(val))
	  d.setDayOfYear(val); // requires gaia_date.js
      break;
      
      case 'hour':
      d.setHours(val);
      break;
      
      case 'minute':
      d.setMinutes(val);
      break;
      
      case 'second':
      d.setSeconds(val);
      break;
      
      case 'increment':
      d.setTime(d.getTime() + parseInt(val));
      break;

    case 'submit':
      break;

      default:
      gaia.log("gaiaDate.dateControl.callback(): Unknown control element: "
	       + type);
      break;
    }
  }
  
  // set, checking earliest/latest dates, then refresh
  this.setDate(d, (this.immediateUpdate || type == 'submit' || doSetDate));
 
  return true;
};


gaiaDate.dateControl.prototype.refreshControls = function (elemList) {
  if (!elemList)
    elemList = this.elements;
  else
    if (elemList.constructor != Array)
      elemList = [ elemList ];
  
  for (var i = 0; i < elemList.length; ++i) {
    var elem = elemList[i];
    elem.disabled = this.disabled;
    var type = elem.gaiaDateControl.type;
    var val = NaN;

    if (this.utc) 
      switch (type) {
      case 'year':
	val = this.date.getUTCFullYear();
	break;
      case 'month':
	val = this.date.getUTCMonth();
	break;
      case 'dom':
	val = this.date.getUTCDate();
	break;
      case 'doy':
	val = gaiaDate.sprintf(elem.gaiaDateControl.fstr,
			       this.date.getUTCDayOfYear());
	break;
      case 'hour':
	val = this.date.getUTCHours();
	break;
      case 'minute':
	val = this.date.getUTCMinutes();
	break;
      case 'second':
	val = this.date.getUTCSeconds();
      case 'increment':
      case 'submit':
	break;
      default:
	gaia.log("gaiaDate.dateControl.refreshControls(): "
		 + "Unknown control element: " + type);
	break;
      }
    else 
      switch (type) {
      case 'year':
	val = this.date.getFullYear();
	break;
      case 'month':
	val = this.date.getMonth();
	break;
      case 'dom':
	val = this.date.getDate();
	break;
      case 'doy':
	val = gaiaDate.sprintf(elem.gaiaDateControl.fstr,
			       this.date.getDayOfYear());
	break;
      case 'hour':
	val = this.date.getHours();
	break;
      case 'minute':
	val = this.date.getMinutes();
	break;
      case 'second':
	val = this.date.getSeconds();
	break;
      case 'increment':
	break;
      default:
	gaia.log("gaiaDate.dateControl.refreshControls(): "
		 + "Unknown control element: " + type);
	break;
      }
    
    switch (elem.tagName.toLowerCase()) {
    case "input":
      elem.value = val;
      break;
      
    case "select":
      var found = false;
      for (var j = 0; j < elem.options.length; ++j) {
	if (elem.options[j].value == val) {
	  elem.selectedIndex = j;
	  found = true;
	  break;
	}
      }
      if (!found) {
	gaia.log("gaiaDate.dateControl.refreshControls(): Could not "
		 + "find option with value " + val 
		 + " for control of type " + elemList[i].gaiaDateControl.type);
      }
      break;
      
      case "button":
      break;
      
      default:
      gaia.log("gaiaDate.dateControl.refreshControls(): Unsupported "
	       + "element type: " + elem.tagName);
      break;
    }
  }
  
  return true;
};


// Remove all decendents (ie children,, grand children etc)
// Static function
gaiaDate.dateControl.removeAllDescendents = function (node) {
  while (node.hasChildNodes()) {
    gaiaDate.dateControl.removeAllDescendents(node.firstChild);
    node.removeChild(node.firstChild);
  }
  return;
}


gaiaDate.dateControl.prototype.yearControl = function(type) {
  var r;

  if (!type)
    type = 'menu';
  
  if (type == 'input') {
    r = this.document.createElement('input');
    r.gaiaDateControl = {'type': 'year'};
    r.type = "text";
    this.refreshControls(r);
  }
  else {
    // anything else means menu
    r = this.document.createElement('select');
    r.gaiaDateControl = {'type': 'year'};
    this.yearControlCreateOptions(r); // calls refresh
  }
  
  r.title = 'Year';

  // Create a closure for the callback
  var obj = this;
  r.onchange = function () { return obj.callback(this); };
  this.elements.push(r);
  return r;
};


gaiaDate.dateControl.prototype.yearControlCreateOptions = function (elem) {
  if (elem.tagName.toLowerCase() != 'select') 
    return null;
  
  // remove all descendents
  gaiaDate.dateControl.removeAllDescendents(elem);
  
  var y1;
  var y2;
  if (this.utc) {
    y1 = this.earliestDate.getUTCFullYear();
    y2 = this.latestDate.getUTCFullYear();
  }
  else {
    y1 = this.earliestDate.getFullYear();
    y2 = this.latestDate.getFullYear();
  }
  for (var i = y1; i <= y2; ++i) {
    var opt = this.document.createElement('option');
    opt.value = i;
    opt.appendChild(this.document.createTextNode(i));
    elem.appendChild(opt);
  }
  this.refreshControls(elem);
  return elem;
};


// Create a control to select the month. Optional format string can be
// used to control how the month is printed.
gaiaDate.dateControl.prototype.monthControl = function(fstr) {
  var r;
  if (!fstr)
    fstr = '%m';
  
  r = this.document.createElement('select');
  var t = new Date(Date.UTC(2000, 0, 1));
  for (var i = 0; i < 12; ++i) {
    var opt = this.document.createElement('option');
    t.setUTCMonth(i);
    opt.value = i;
    opt.appendChild(this.document.createTextNode(t.UTCstrftime(fstr)));
    r.appendChild(opt);
  }

  r.gaiaDateControl = {'type': 'month',
		       'fstr': fstr};
  r.title = 'Month';

  var obj = this;
  r.onchange = function () { return obj.callback(this); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};


// Create a control to select the day of month. Optional format string
// can be used to control how the number is printed.
gaiaDate.dateControl.prototype.domControl = function(fstr) {
  var r;
  if (!fstr)
    fstr = '%02d';
  
  r = this.document.createElement('select');
  for (var i = 1; i <= 31 ; ++i) {
    var opt = this.document.createElement('option');
    opt.value = i;
    opt.appendChild(this.document.createTextNode(gaiaDate.sprintf(fstr, i)));
    r.appendChild(opt);
  }
  
  r.gaiaDateControl = {'type': 'dom',
		       'fstr': fstr};
  r.title = 'Day of month';
  var obj = this;
  r.onchange = function () { return obj.callback(this); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};

// Create a control to select the day of year. Optional format string
// can be used to control how the number is printed.
gaiaDate.dateControl.prototype.doyControl = function(fstr) {
  var r;
  if (!fstr)
    fstr = '%03d';
  
  r = this.document.createElement('input');
  r.type = "text";
  r.gaiaDateControl = {'type': 'doy',
		       'fstr': fstr};
  r.title = 'Day of year';
  r.size = 4;
  r.maxlength = 3;
  var obj = this;
  r.onchange = function () { return obj.callback(this); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};


gaiaDate.dateControl.prototype.hourControl = function(fstr) {
  var r;
  if (!fstr)
    fstr = '%02d';
  
  r = this.document.createElement('select');
  for (var i = 0; i < 24 ; ++i) {
    var opt = this.document.createElement('option');
    opt.value = i;
    opt.appendChild(this.document.createTextNode(gaiaDate.sprintf(fstr, i)));
    r.appendChild(opt);
  }
  
  r.gaiaDateControl = {'type': 'hour',
		       'fstr': fstr};
  r.title = 'Hour';
  var obj = this;
  r.onchange = function () { return obj.callback(this); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};


gaiaDate.dateControl.prototype.minuteControl = function(fstr) {
  var r;
  if (!fstr)
    fstr = '%02d';
  
  r = this.document.createElement('select');
  for (var i = 0; i < 60 ; ++i) {
    var opt = this.document.createElement('option');
    opt.value = i;
    opt.appendChild(this.document.createTextNode(gaiaDate.sprintf(fstr, i)));
    r.appendChild(opt);
  }
  
  r.gaiaDateControl = {'type': 'minute',
		       'fstr': fstr};
  r.title = 'Minute';
  var obj = this;
  r.onchange = function () { return obj.callback(this); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};

gaiaDate.dateControl.prototype.secondControl = function(fstr) {
  var r;
  if (!fstr)
    fstr = '%02d';
  
  r = this.document.createElement('select');
  for (var i = 0; i < 60 ; ++i) {
    var opt = this.document.createElement('option');
    opt.value = i;
    opt.appendChild(this.document.createTextNode(gaiaDate.sprintf(fstr, i)));
    r.appendChild(opt);
  }
  
  r.gaiaDateControl = {'type': 'second',
		       'fstr': fstr};
  r.title = 'Second';
  var obj = this;
  r.onchange = function () { return obj.callback(this); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};


// Get a buttons for incrementing the date. Label and increment value
// should be defined. If immediate is set true then it will alter the
// internal state and call any user callbacks (ie it acts as both an
// increment button and a submit buttons). If false only the internal
// state is adjusted. Note that when immediateUpdate mode is in
// operation all icnrement buttons act as submit buttons.
gaiaDate.dateControl.prototype.incrementControl = 
  function(label, ms, immediate) {
  // Internet explorer uses the value attribute as the label! Work
  // around by passing the increment value to the callback function.
  var r;
  if (!label)
    label = '?';
  
  ms = parseInt(ms);
  if (!isFinite(ms))
    ms = 0;
  
  if (immediate === null || immediate === void 0)
    immediate = this.immediateUpdate;

  r = this.document.createElement('button');
  r.appendChild(this.document.createTextNode(label));
  r.gaiaDateControl = {'type': 'increment'};
  r.title = label;

  var obj = this;
  r.onclick = function () { return obj.callback(this, ms, immediate); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};


gaiaDate.dateControl.prototype.submitControl = function(label) {
  var r;
  if (!label)
    label = 'Submit';
  
  r = this.document.createElement('button');
  r.appendChild(this.document.createTextNode(label));
  r.gaiaDateControl = {'type': 'submit'};
  r.title = label;

  var obj = this;
  r.onclick = function () { return obj.callback(this); };
  this.elements.push(r);
  this.refreshControls(r);
  return r;
};



// A date range control. We use two date controls and trap their
// callbacks to ensure starttime is never later than the end time, and
// other sensible behaviour.

gaiaDate.dateRangeControl = function(obj) {
  if (!obj)
    obj = new Object;
  this.userCallback = obj.callback;
  obj.callback = null;

  // Allow for control to be updated immediately or for a single 'Go'
  // button to activate the callback. For private use have both
  // start/end dte controls working in immediate update mode.
  if (obj.immediateUpdate != null)
    this.immediateUpdate = (obj.immediateUpdate == true);
  else
    this.immediateUpdate = true;
  obj.immediateUpdate = true; 

  if (obj.document)
    this.document = obj.document;
  else 
    this.document = obj.document = window.document;

  this.startControl = new gaiaDate.dateControl(obj);
  this.endControl = new gaiaDate.dateControl(obj);
  
  // The dateControl "user" callback needs a closure function, which
  // unfortunately introduces a cyclic reference. However, the date
  // control unsets the callback as part of its destructor process, so
  // we don't need to worry.
  var t = this;
  this.startControl.setCallback(function () {t.callback("startControl")});
  this.endControl.setCallback(function () {t.callback("endControl")});
};


gaiaDate.dateRangeControl.prototype.destructor = function ( ) {
  this.startControl.destructor();
  this.endControl.destructor();
  this.startControl = this.endControl = null;

  // remove user callback as it may form cyclic references
  this.userCallback = null;

  return true;
};


gaiaDate.dateRangeControl.prototype.toString = function () {
  return this.startControl.toString() + ' - ' + this.endControl.toString();
};


gaiaDate.dateRangeControl.prototype.getDisabled = function () {
  return this.startControl.getDisabled();
};


gaiaDate.dateRangeControl.prototype.setDisabled = function (a) {
  this.startControl.setDisabled(a);
  return this.endControl.setDisabled(a);
};


gaiaDate.dateRangeControl.prototype.getDate = function ( ) {
  return [this.startControl.getDate(), this.endControl.getDate()];
};


gaiaDate.dateRangeControl.prototype.getStartDate = function ( ) {
  return this.startControl.getDate();
};

gaiaDate.dateRangeControl.prototype.getEndDate = function ( ) {
  return this.endControl.getDate();
};


gaiaDate.dateRangeControl.prototype.getEarliestDate = function ( ) {
  return this.startControl.getEarliestDate();
};

gaiaDate.dateRangeControl.prototype.getLatestDate = function ( ) {
  return this.startControl.getLatestDate();
};


gaiaDate.dateRangeControl.prototype.setStartDate = function (d, doCallback) {
  if (doCallback === null || doCallback == void 0)
    doCallback = this.immediateUpdate;

  var r = this.startControl.setDate(d, false);
  if (doCallback) 
    this.doUserCallback();
    
  return r;
};


gaiaDate.dateRangeControl.prototype.setEndDate = function (d, doCallback) {
  if (doCallback === null || doCallback == void 0)
    doCallback = this.immediateUpdate;

  var r = this.endControl.setDate(d, false);
  if (doCallback) 
    this.doUserCallback();
    
  return r;
};



gaiaDate.dateRangeControl.prototype.getImmediateUpdate = function ( ) {
  return this.immediateUpdate;
};


gaiaDate.dateRangeControl.prototype.setImmediateUpdate = function (s) {
  var r = this.immediateUpdate;
  this.immediateUpdate = (s == true);
  return r;
};


gaiaDate.dateRangeControl.prototype.setCallback = function (f) {
  var r = this.userCallback;
  this.userCallback = f;
  return r;
};


gaiaDate.dateRangeControl.prototype.callback = function(type) {
  var st = this.startControl.getDate();
  var et = this.endControl.getDate()
  
  var doCallback = (this.immediateUpdate && this.userCallback);
  switch (type) {
  case "startControl":
    if (et.valueOf() < st.valueOf())
      this.endControl.setDate(st, false);
    break;
    
  case "endControl":
    if (st.valueOf() > et.valueOf())
      this.startControl.setDate(et, false);
    break;
    
  case "submit":
    doCallback = true;
    break;

  default:
    console.warn("Unknown control type");
    return false;
  }

  if (doCallback) 
    this.doUserCallback();

  return true;
};


gaiaDate.dateRangeControl.prototype.doUserCallback = function () {
  if (typeof this.userCallback == "function")
    return this.userCallback(this);
  if (typeof this.userCallback == "string")
    return eval(this.userCallback);
  return null;
};

gaiaDate.dateRangeControl.prototype.startYearControl = function (type) {
  return this.startControl.yearControl(type);
};

gaiaDate.dateRangeControl.prototype.endYearControl = function (type) {
  return this.endControl.yearControl(type);
};

gaiaDate.dateRangeControl.prototype.startMonthControl = function (fstr) {
  return this.startControl.monthControl(fstr);
};

gaiaDate.dateRangeControl.prototype.endMonthControl = function (fstr) {
  return this.endControl.monthControl(fstr);
};

gaiaDate.dateRangeControl.prototype.startDomControl = function (fstr) {
  return this.startControl.domControl(fstr);
};

gaiaDate.dateRangeControl.prototype.endDomControl = function (fstr) {
  return this.endControl.domControl(fstr);
};

gaiaDate.dateRangeControl.prototype.startDoyControl = function (fstr) {
  return this.startControl.doyControl(fstr);
};

gaiaDate.dateRangeControl.prototype.endDoyControl = function (fstr) {
  return this.endControl.doyControl(fstr);
};


gaiaDate.dateRangeControl.prototype.startHourControl = function (fstr) {
  return this.startControl.hourControl(fstr);
};

gaiaDate.dateRangeControl.prototype.endHourControl = function (fstr) {
  return this.endControl.hourControl(fstr);
};

gaiaDate.dateRangeControl.prototype.startMinuteControl = function (fstr) {
  return this.startControl.minuteControl(fstr);
};

gaiaDate.dateRangeControl.prototype.endMinuteControl = function (fstr) {
  return this.endControl.minuteControl(fstr);
};

gaiaDate.dateRangeControl.prototype.startSecondControl = function (fstr) {
  return this.startControl.secondControl(fstr);
};

gaiaDate.dateRangeControl.prototype.endSecondControl = function (fstr) {
  return this.endControl.secondControl(fstr);
};

gaiaDate.dateRangeControl.prototype.startIncrementControl = 
  function (label, ms, immediate) {
  return this.startControl.incrementControl(label, ms, immediate);
};

gaiaDate.dateRangeControl.prototype.endIncrementControl = 
  function (label, ms, immediate) {
  return this.endControl.incrementControl(label, ms, immediate);
};


gaiaDate.dateRangeControl.prototype.submitControl = function (label) {
  var r;
  if (!label)
    label = 'Submit';
  
  r = this.document.createElement('button');
  r.appendChild(this.document.createTextNode(label));
  r.title = label;

  var obj = this;
  r.onclick = function () { return obj.callback("submit"); };
  return r;
};

