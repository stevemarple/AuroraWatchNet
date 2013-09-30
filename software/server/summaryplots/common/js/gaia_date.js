/* A library of useful Date functions. The following member functions
 * are added to the Date class (unless already present):
 *
 * isLeapYear(): indicates if in local time date is a leap year
 * isUTCLeapYear(): indicates if in UTC time date is a leap year
 *
 * getDayOfYear(): returns day of year, in local time
 * getUTCDayOfYear(): returns day of year, in UTC time
 *
 * strftime(fstr): JavaScript equivalent of the POSIX strftime function.
 * UTCstrftime(fstr): as above, but returns UTC year, month day etc.
 *
 *
 * In addition the following functions are available:
 *
 * gaiaDate.isLeapYear()
 * gaiaDate.isLeapYear() 
 * gaiaDate.calendar()
 * gaiaDate.getDayOfYear(year, month, day)
 * gaiaDate.strftime()
 * gaiaDate.isInteger()
 * gaiaDate.isValid()
 * gaiaDate.ISOStringToUTCDate()
 * 
 * To avoid potential conflicts with other JavaScript functions all
 * private functions are stored in a global object "gaiaDate".
 */

if (!window.gaiaDate) 
  var gaiaDate = { };

gaiaDate.log = function ( ) {
  if (window.console && window.console.log)
    return window.console.log.apply(this, arguments);
  return null;
};

gaiaDate.warn = function ( ) {
  if (window.console && window.console.warn)
    return window.console.warn.apply(this, arguments);
  return null;
};

gaiaDate.toNumber = function (a) {
  if (typeof a == "object")
    for (var n in a)
      a[n] = parseFloat(a[n]);
  else
    a = parseFloat(a);
  if (a === null || a === undefined)
    a = NaN;
  return a;
};

gaiaDate.isLeapYear = function (y) {
  y = gaiaDate.toNumber(y);
  y |= 0; // convert to integer;
  return y % 4 == 0 && (y % 400 == 0 || y % 100 != 0);
};


// Return number of days in each month for given year
gaiaDate.calendar = function (year) {
  var a = new Array(31, 28, 31,
		    30, 31, 30,
		    31, 31, 30,
		    31, 30, 31);
  
  if(gaiaDate.isLeapYear(year)) 
    a[1] = 29;
  return a;
};


// Calculate day of year. Month, day and doy all start at 1.
gaiaDate.getDayOfYear = function (year, month, day) {
  year = gaiaDate.toNumber(year);
  month = gaiaDate.toNumber(month);
  day = gaiaDate.toNumber(day);
  if (!gaiaDate.isValid(year, month, day))
    return NaN;
  
  var c = gaiaDate.calendar(year);
  var doy = 0;
  for(var m = 0; m < month-1; ++m) {
    doy += c[m];
  }
  
  doy += day;
  return doy;
};


gaiaDate.yearDayOfYearToDate = function (year, doy) {
  year = gaiaDate.toNumber(year);
  doy = gaiaDate.toNumber(doy);
  if (!gaiaDate.isInteger(year) || !gaiaDate.isInteger(doy)) {
    gaiaDate.log('not integer');
    return null;
  }
  var c = gaiaDate.calendar(year);
    
  if (doy < 1)
    return null;

  if (c[1] == 29) {
    // leap year
    if (doy > 366)
      return null;
  }
  else
    if (doy > 365)
      return null;
    
  var m = -1;
  var dom = 0;
  for (var n = 0; n < 12; ++n) {
    if (doy > c[n]) {
      doy -= c[n];
      m = n;
    }
    else {
      dom = doy;
      break;
    }
  }
    
  ++m; // add one to month (for part of month), in range 0-11
  return new Date(year, m, dom);
};


// Define names for motnhs and days of week
gaiaDate.daysOfWeek = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 
		       'Thursday', 'Friday', 'Saturday'];
gaiaDate.daysOfWeekShort = ['Sun', 'Mon', 'Tue', 'Wed', 
			    'Thu', 'Fri', 'Sat'];
  
gaiaDate.monthNames = ['January', 'February', 'March', 
		       'April', 'May', 'June', 
		       'July', 'August', 'September', 
		       'October', 'November', 'December'];
gaiaDate.monthNamesShort = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
			    'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];


// Private strftime function. utc if a flag indicating if UTC output
// is required.
gaiaDate.strftime = function (t, fstr, utc) {
  if (utc === null)
    utc = false;
  var s = '';
  
  if (typeof fstr != 'string') {
    gaiaDate.log('fstr not a string');
    return null;
  }
    
  var i = 0;
  var s = '';
  var tmp;
  while (i < fstr.length) {
    var c = fstr.charAt(i);
    if (c == '%') {
      // look to next char
      ++i;
      c = fstr.charAt(i);
	    
      switch (c) {
      case '%':
	s += '%';
	break;
		
      case 'a':
	// Abbreviated day name
	s += gaiaDate.daysOfWeekShort[utc ? t.getUTCDay() : t.getDay()];
	break;
		
      case 'A':
	// Full day name
	s += gaiaDate.daysOfWeek[utc ? t.getUTCDay() : t.getDay()];
	break;

      case 'b':
	// Abbreviated month name
	s += gaiaDate.monthNamesShort[utc ? t.getUTCMonth() : t.getMonth()];
	break;

      case 'B':
	// Full month name
	s += gaiaDate.monthNames[utc ? t.getUTCMonth() : t.getMonth()];
	break;

      case 'd':
	// Day of month
	tmp = (utc ? t.getUTCDate() : t.getDate());
	if (tmp >= 10)
	  s += tmp;
	else 
	  s += '0' + tmp;
	break;

      case 'H':
	// Hour
	tmp = (utc ? t.getUTCHours() : t.getHours());
	if (tmp >= 10)
	  s += tmp;
	else
	  s += '0' + tmp;
	break;

      case 'j':
	// Day of year
	tmp = (utc ? t.getUTCDayOfYear() : t.getDayOfYear());
	if (tmp >= 100)
	  s += tmp;
	else {
	  if (tmp >= 10)
	    s += '0' + tmp;
	  else
	    s += '00' + tmp;
	}
	break;

      case 'm':
	// Month
	tmp = (utc ? t.getUTCMonth() : t.getMonth()) + 1;
	if (tmp >= 10)
	  s += tmp;
	else
	  s += '0' + tmp;
	break;

      case 'M':
	// Minutes
	tmp = (utc ? t.getUTCMinutes() : t.getMinutes());
	if (tmp >= 10)
	  s += tmp;
	else
	  s += '0' + tmp;
	break;

      case 's':
	// Integer seconds since unix epoch
	tmp = parseInt(t.getTime() / 1000);
	s += tmp;
	break;

      case 'S':
	// Seconds
	tmp = (utc ? t.getUTCSeconds() : t.getSeconds());
	if (tmp >= 10)
	  s += tmp;
	else
	  s += '0' + tmp;
	break;

      case 'y':
	s += ((utc ? t.getUTCFullYear() : t.getFullYear()) % 100);
	break;

      case 'Y':
	s += (utc ? t.getUTCFullYear() : t.getFullYear());
	break;

      default:
	gaiaDate.warn('unknown format specifier: ' + c);
	s += '%' + c;

      };
    }
    else {
      s += c;
    }
	
	
    ++i;
  }
   
  return s;
};
  

// Test if a value is an integer or not. Valid range is within 32
// bit integer values only, which is good enough for the component
// parts of Date. Function takes advantage that logical operations
// implicitly convert to 32 bit integers.
gaiaDate.isInteger = function (a) {
  return (a == (a | 0));
};
  
// Test if a date is valid. Pass year, month, day, [hour, minute,
// second], or an array of those values
gaiaDate.isValid = function() {
  var arg;
  if (arguments.length == 1 && arguments[0].constructor == Date) {
    return isFinite(arguments[0].valueOf());
  }

  if (arguments.length == 1 && typeof arguments[0] == "object"
      && arguments[0].constructor == Array)
    arg = arguments[0];
  else
    arg = arguments;

  if (arg.length != 3 && arg.length != 6) 
    return false; // Incorrect number of values, must be  bad date
    
  // Test if year, month, day, hour, and minute have integer values
  for (var i = 0; i < (arg.length > 5 ? 5 : arg.length); ++i)
    if (!gaiaDate.isInteger(arg[i]))
      return false;
    else 
      // convert any non-numeric types to integer (take advatange
      // that logical operation convert internally to int32)
      arg[i] |= 0; 

  // Assume year is correct as it is integer
   
  // Test month
  if (arg[1] < 1 || arg[1] > 12)
    return false;

  // Test day of month
  var cal = gaiaDate.calendar(arg[0]);
  if (arg[2] < 1 || arg[2] > (gaiaDate.calendar(arg[0]))[arg[1]-1])
    return false;
    
  if (arg.length == 6) {
    if (arg[3] < 0 || arg[3] > 23)
      return false; // hours not valid
    if (arg[4] < 0 || arg[4] > 59)
      return false; // minutes not valid
      
    if (arg[5] < 0 || arg[5] > 60)
      // Let any leap seconds be valid
      return false;
  }
    
  return true;
};
  
gaiaDate.ISOStringToUTCDate = function (s) {
  if (s !== null && s !== undefined && s.constructor == Date)
    return s;

  var pattern = 
  // 1       2       3      4    5       6       7     8     
  /^(\d{4})-(\d{2})-(\d{2})([tT](\d{2}):(\d{2}):(\d{2}(\.\d+)))?[zZ]?/;
  var m = s.match(pattern);
  if (m === null) {
    gaiaDate.log('bad ISO date string: ' + s);
    return null;
  }
    
  var ymdhms = [m[1], m[2], m[3], m[5], m[6], m[7]];
  for (var i = 0; i < ymdhms.length; ++i)
    if (ymdhms[i] === null || ymdhms[i] === undefined)
      ymdhms[i] = 0;
    
  var year = m[1];
  var month = m[2];
  var day = m[3];
  var hour = m[5];
  var minute = m[6];
  var second = m[7];
    
  if (year === null || year === undefined)
    year = 0;
  if (month === null || month === undefined)
    month = 0;
  if (day === null || day === undefined)
    day = 0;
  if (hour === null || hour === undefined)
    hour = 0;
  if (minute === null || minute === undefined)
    minute = 0;
  if (second === null || second === undefined)
    second = 0;

  return new Date(Date.UTC(year, month-1, day, hour, minute, second, 0));
};
  
gaiaDate.getStartOfDay = function (d) {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
};

gaiaDate.getUTCStartOfDay = function (d) {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), 
			   d.getUTCDate()));
};

gaiaDate.getToday = function () {
  return new gaiaDate.getStartOfDay(new Date);
};

gaiaDate.getUTCToday = function () {
  return new gaiaDate.getUTCStartOfDay(new Date);
};

gaiaDate.getYesterday = function () {
  return new gaiaDate.getStartOfDay(new Date((new Date).valueOf() - 86400e3));
};

gaiaDate.getUTCYesterday = function () {
  return new gaiaDate.getUTCStartOfDay(new Date((new Date).valueOf() 
					      - 86400e3));
};

gaiaDate.getTomorrow = function () {
  return new gaiaDate.getStartOfDay(new Date((new Date).valueOf() 
					   + 86400e3));
};

gaiaDate.getUTCTomorrow = function () {
  return new gaiaDate.getUTCStartOfDay(new Date((new Date).valueOf() 
					      + 86400e3));
};

gaiaDate.areEqual = function (a, b) {
  return a.valueOf() == b.valueOf();
};

gaiaDate.round = function (t, duration) {
  duration = parseFloat(duration); // in milliseconds
  var s = t.valueOf();
  return new Date(Math.round(t.valueOf() / duration) * duration);
};
  
gaiaDate.installDateMemberFunctions = function (d) {

  if (!d)
    d = new Date;
  var dp = d.constructor.prototype;
	
  // Create Date.isLeapYear() if it does not already exist
  if (!("isLeapYear" in d)) {
    dp.isLeapYear = function () { 
      return gaiaDate.isLeapYear(this.getFullYear());
    };
  }
    
  // Create Date.isUTCLeapYear() if it does not already exist
  if (!("isUTCLeapYear" in d)) {
    dp.isUTCLeapYear = function () { 
      return gaiaDate.isLeapYear(this.getUTCFullYear());
    };
  }
    
  // Create Date.getDayOfYear() if it does not already exist
  if (!("getDayOfYear" in d)) {
    dp.getDayOfYear = function () { 
      return gaiaDate.getDayOfYear(this.getFullYear(),
				   this.getMonth() + 1,
				   this.getDate());
    };
  }
  
  // Create Date.getUTCDayOfYear() if it does not already exist
  if (!("getUTCDayOfYear" in d)) {
    dp.getUTCDayOfYear = function () { 
      return gaiaDate.getDayOfYear(this.getUTCFullYear(),
				   this.getUTCMonth() + 1,
				   this.getUTCDate());
    };
  }

  // Create Date.setDayOfYear() if it does not already exist
  if (!("setDayOfYear" in d)) {
    dp.setDayOfYear = function (doy) { 
      var a = gaiaDate.yearDayOfYearToDate(this.getFullYear(), doy);
      a.setHours(this.getHours());
      a.setMinutes(this.getMinutes());
      a.setSeconds(this.getSeconds());
      a.setMilliseconds(this.getMilliseconds());
      return this.setTime(a.getTime());
    };
  }
  // Create Date.setDayOfYear() if it does not already exist
  if (!("setUTCDayOfYear" in d)) {
    dp.setUTCDayOfYear = function (doy) { 
      var a = gaiaDate.yearDayOfYearToDate(this.getUTCFullYear(), doy);
      a.setUTCHours(this.getUTCHours());
      a.setUTCMinutes(this.getUTCMinutes());
      a.setUTCMilliseconds(this.getUTCMilliseconds());
      return this.setTime(a.getTime());
    };
  }

  // Create Date.strftime() if it does not already exist
  if (!("strftime" in d)) {
    dp.strftime = function (fstr) { 
      return gaiaDate.strftime(this, fstr, false);
    };
  }
    
  // Create Date.UTCstrftime() if it does not already exist
  if (!("UTCstrftime" in d)) {
    dp.UTCstrftime = function (fstr) { 
      return gaiaDate.strftime(this, fstr, true);
    };
  }
   
};
  
  
gaiaDate.installDateMemberFunctions(new Date);


