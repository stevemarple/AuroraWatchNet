/* A strftime library.
 *
 * The following functions are placed in gaiaSprintf:
 *
 * gaiaSprintf.sprintf()
 *
 * To avoid potential conflicts with other JavaScript functions all
 * private functions are stored in a global object
 * "gaiaSprintf". Users should import the sprintf function into the
 * window namespace themselves.
 */


if (!window.gaiaSprintf) {
  var gaiaSprintf = { };
  
  gaiaSprintf.log = function ( ) {
    if (window.console && window.console.log)
      return window.console.log.apply(this, arguments);
    return null;
  };
  
  gaiaSprintf.warn = function ( ) {
    if (window.console && window.console.warn)
      return window.console.warn.apply(this, arguments);
    return null;
  };

  gaiaSprintf.sprintf = function ( ){
    var arg = new Array;
    var len = arguments.length;
    for (var i = 0; i < len; ++i)
      arg[i] = arguments[i];
  
    if (arg.length == 0)
      return '';


    var fstr = arg.shift();
    if (typeof fstr != "string") {
      gaiaSprintf.log("format string is not a string");
      return '';
    }
  
  
    var argNum = 0; // argument to be processed
    var i = 0;  // counter for position in format string
    var s = ''; // output string
    var tmp;
    var c;
    while (i < fstr.length) {
      c = fstr.charAt(i);
      if (c == "%") {
	// format specifier follows
	if (fstr.charAt(i+1) == "%") {
	  // an escaped % character
	  s += "%";
	  ++i;
	}
	else {
	  // Find the format specifer string. The specifier follows
	  // the description of the glibc man page for sprintf
	  //              1             23          4    5          6 78       9    a           b          c            
	  var pattern = /^([#0 +-]{0,5})(([1-9]\d*)|(\*)|(\*\d+\$))?(.((-?\d+)|(\*)|(\*\d+\$)))?([diouxX]?)([diouxXeEfFgGaAcspn])/;
	  var substr = fstr.substr(i+1);
	  var m = substr.match(pattern);
	  if (m === null) {
	    gaiaSprintf.warn('bad format specifer: %' + substr);
	    s += '%' + substr;
	    ++i;
	  }
	  else {
	    var flags = m[1];
	    var altForm = flags.match(/#/);
	    var zeroPadding = flags.match(/0/);
	    var leftAdjust = flags.match(/-/);
	    var blank = flags.match(/ /);
	    var signAll = flags.match(/\+/);
	  
	    var width = m[2];
	    var widthValue = parseInt(width, 10);
	    if (width == '*') {
	      widthValue = arg[argNum++];
	    }
	    else {
	      if (width !== undefined) {
		var wm = width.match(/^\*(\d+)\$$/);
		if (pm) 
		  // take m-th parameter
		  widthValue = arg[parseInt(wm[1], 10)];
	      }
	    }
	    if (widthValue < 0 || isNaN(widthValue))
	      widthValue = 0;

	    var precision = m[7];
	    var precisionValue = parseInt(precision, 10);
	    if (precision == "*") {
	      precisionValue = arg[argNum++];
	    }
	    else {
	      if (precision !== undefined) {
		var pm = precision.match(/^\*(\d+)\$$/);
		if (pm) 
		  // take m-th parameter
		  precisionValue = arg[parseInt(pm[1], 10)];
	      }
	    }
	    if (precisionValue < 0 || isNaN(precisionValue))
	      precisionValue = 0;

	    // length modifers are ignored
	    var lengthModifier = m[11];
	    var conversion = m[12];
	    var x = arg[argNum];

	    var padChar = ' ';
	    if (zeroPadding)
	      padChar = '0';
	  
	    /*
	      gaiaSprintf.log('conversion: ' + conversion);
	      gaiaSprintf.log('widthValue: ' + widthValue);
	      gaiaSprintf.log('precisionValue: ' + precisionValue);
	      gaiaSprintf.log('precision: ' + precision);
	    */
	    switch (conversion) {
	    case 'd':
	    case 'i':
	      // "d, i: integer converted to signed decimal"
	      x = Math.round(x);
	      tmp = x.toString(10);
	      if (signAll && x > 0)
		tmp = '+' + x;
	      //  "The default precision is 1.  When 0 is printed with
	      //  an explicit precision 0, the output is empty."
	      if (x == 0 && precision == 0)
		tmp = '';
	      break;
	    
	    case 'o':
	      // "o: (unsigned) integer converted to octal." Accept and
	      // handle negative numbers too
	      x = Math.round(x);
	      tmp = x.toString(8);
	      if (signAll && x > 0)
		tmp = '+' + x;
	      break;
	      //  "The default precision is 1.  When 0 is printed with
	      //  an explicit precision 0, the output is empty."
	      if (x == 0 && precision == 0)
		tmp = '';

	    case 'x':
	    case 'X':
	      // "x: (unsigned) integer converted to hexadecimal." Accept and
	      // handle negative numbers too
	      x = Math.round(x);
	      tmp = x.toString(16);
	      if (signAll && x > 0)
		tmp = '+' + x;
	      break;

	      if (altForm)
		tmp = '0x' + tmp;
	    
	      //  "The default precision is 1.  When 0 is printed with
	      //  an explicit precision 0, the output is empty."
	      if (x == 0 && precision == 0)
		tmp = '';

	      // Set case. One of these conversions is redundant - but
	      // is it the same for all browsers? Play safe.
	      if (conversion == "X")
		tmp = tmp.toUpperCase();
	      else
		tmp = tmp.toLowerCase();
	      break;

	    case 'e':
	    case 'E':
	      // "e, E: The double argument is rounded and converted in
	      // the style [-]d.ddde+-dd"
	      if (precision === undefined)
		// "if the precision is missing, it is taken as 6"
		precisionValue = 6; 

	      tmp = x.toExponential(precisionValue);
	      if (signAll && x > 0)
		tmp = '+' + x;
	    
	      if (isFinite(x)) {
		if (conversion == 'E')
		  tmp = tmp.toLowerCase();
		else
		  tmp = tmp.toLowerCase();
	      }
	      break;

	    case 'f':
	    case 'F':
	      // "f, F: The double argument is rounded and converted to
	      // decimal notation in the style [-]ddd.ddd
	      if (precision === undefined)
		// "if the precision is missing, it is taken as 6"
		precisionValue = 6; 

	      tmp = x.toFixed(precisionValue);
	      if (signAll && x > 0)
		tmp = '+' + x;
	    
	      break;
	    
	    case 'g':
	    case 'G':
	      // "g, G: The double argument is converted in style f or e
	      // (or F or E for G conversions)".
	    
	      // Although the man page states when e (or E) conversion
	      // should be used don't get hung up on details here, let
	      // JavaScript do its best.

	      // "If the precision is missing, 6 digits are given; if the
	      // precision is zero, it is treated as 1."
	      if (precision === undefined)
		precisionValue = 6; 
	      else
		if (precisionValue == 0)
		  precisionValue = 1;
	    
	      tmp = x.toExponential(precisionValue);
	      if (signAll && x > 0)
		tmp = '+' + x;
	    
	      if (isFinite(x)) {
		if (conversion == 'E')
		  tmp = tmp.toLowerCase();
		else
		  tmp = tmp.toLowerCase();
	      }
	      break;
	    
	    case 'a':
	    case 'A':
	      // "For a conversion, the double argument is converted to
	      // hexadecimal notation (using the letters abcdef) in the
	      // style [-]0xh.hhhhp+-d; for A conversion the prefix 0X,
	      // the letters ABCDEF, and the exponent separator P is
	      // used."
	    
	      tmp = x.toString(16);
	      if (signAll && x > 0)
		tmp = '+' + x;

	      //  "The default precision is 1.  When 0 is printed with
	      //  an explicit precision 0, the output is empty."
	      if (x == 0 && precision == 0)
		tmp = '';
	      break;

	    case 'c':
	      // Output single character
	      padChar = ' ';
	      tmp = '' + x;
	      tmp = tmp.charAt(0);
	      break;

	    case 's':
	      padChar = ' ';
	      tmp = '' + x;
	      break;
	    
	    case 'p':
	      // Void* pointer
	      padChar = ' ';
	      tmp = '0x' + x.toString(16);
	      break;

	    
	    default:
	      gaiaSprintf.log('unknown conversion: ' + conversion);
	      break;
	    }

	    // do any width adjustments
	    if (width && tmp.length < widthValue) {
	      var padding = '';
	      for (var pn = widthValue - tmp.length; pn > 0; --pn)
		padding += padChar;
	    
	      if (leftAdjust)
		tmp += padding;
	      else
		tmp = padding + tmp;
	    }
	    
	    ++argNum;
	    s += tmp;
	  
	    // skip over '%' and remainder of format specifier
	    i += 1 + m[0].length; 
	  }
	
	}
      }
      else {
	// not any sort of special character, output it
	s += c;
	++i;
      }
    }
    return s;
  }


 }
