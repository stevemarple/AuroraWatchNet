/* makeabbrev.c */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <ctype.h>

/*
 * $Log: makeabbrev.c,v $
 * Revision 1.8  1998/11/21 16:11:16  marple
 * Tidied up printing of version string, removed more debugging code.
 *
 * Revision 1.7  1998/11/21 15:34:13  marple
 * Added doc++ style comments, removed debugging code.
 *
 * Revision 1.6  1998/11/21 15:08:21  marple
 * Fixed bug where free() was called on destroyed memory
 *
 * Revision 1.5  1998/11/10 10:01:56  marple
 * Rewrite of insert_node()
 *
 * Revision 1.4  1998/11/08 17:04:50  ega070
 * Various mods
 *
 * Revision 1.3  1997/08/23 00:05:12  ega070
 * added abbrev_short, abbrev_full to node struct
 * insert_node now takes into account abbrev_short and abbrev_full when
 * comparing nodes
 * identical nodes are not inserted into the list
 *
 * Revision 1.2  1997/08/16 14:14:02  ega070
 * writes to file, not stdout
 * input filename can be just basename or with extension
 * writes some information to screen to confirm actions
 *
 * Revision 1.1  1997/08/16 01:51:29  ega070
 * Initial revision
 *
 * Revision 1.1  1997/08/16 01:39:14  ega070
 * Initial revision
 *
 */


/* ***** TYPE DEFINITIONS ***** */

typedef struct node_t {
  char *abbrevitem;
  char *key;
  char *abbrev_short;
  char *abbrev_full;
  struct node_t *next;
} node;

/* ***** FUNCTION PROTOTYPES ***** */
char* read_param(const char *str, int field);
void key_sanity_check(char **key_ptr, const char *abbrev_short);
char* make_abbrevitem(const char *abbrev_short, const char *abbrev_full);
int nodecasecmp(const node *n1, const node *n2);
void insert_node(char *abbrev_short, char *abbrev_full, char *key);
void print_list(FILE *file);
void free_node(node *n);
void free_list(void);
void errmess(const char *message);

/* ***** GLOBAL VARIABLES ***** */
static const char *ERRMESS_NO_MEM = "out of memory";
static const char *INFILE_EXT = ".abb";
static const char *OUTFILE_EXT = ".abr";

/* we only need one list and it is easier to have a global variable
   than pass **node everywhere */
node *list_start; 

/* for debugging it is easiest if this is global */
int line_num = 0;

/* keep the revision string for ident to find */
static const char *revision = "$Revision: 1.8 $";

/* the version string to print */
char *version;

/** Program to sort and format abbreviations used in LaTeX. To be used
 *  with abbrev.sty.
 *  @param Exactly one argument, the file to operate on. May be
 *  specified as file or as file.abb
 *  @name makeabbrev
 *  @author Steve Marple
 *  @version $Revision: 1.8 $ */
int main(int argc, char **argv)
{
  int i;
  long ell;
  long line_start;
  long line_end;
  char *buffer = NULL;
  char *infile_name;
  char *outfile_name;
  char *cptr;
  char *abbrev_short;
  char *abbrev_full;
  char *key;
  FILE *infile;
  FILE *outfile;
  list_start = NULL;

  /* massage revision into a suitable version string */
  version = malloc(sizeof(char) * (strlen(&revision[11]) + 1));
  if(version == NULL)
    errmess(ERRMESS_NO_MEM);
  strcpy(version, &revision[11]);
  version[strlen(version) - 2] = '\0';  /* squish that space */
  
  /* Print out a usage message, GNU say not to use argv[0] as program
     name. */
  if(argc != 2) {
    printf("makeabbrev:\nusage\tmakeabbrev file\n");
    exit(0);
  }

  /* create file names */
  if(!strcmp(&argv[1][strlen(argv[1])-strlen(INFILE_EXT)], INFILE_EXT)) {
    /* filename extension given */
    infile_name = malloc(sizeof(char) * (strlen(argv[1]) + 1));
    outfile_name = malloc(sizeof(char) * (strlen(argv[1])
					  + strlen(OUTFILE_EXT) + 1));
    if(infile_name == NULL || outfile_name == NULL)
      errmess(ERRMESS_NO_MEM);
    strcpy(infile_name, argv[1]);
    strncpy(outfile_name, argv[1], strlen(argv[1])-strlen(INFILE_EXT));
    strcpy(&outfile_name[strlen(argv[1])-strlen(INFILE_EXT)], OUTFILE_EXT);
    
  }
  else {
    infile_name = malloc(sizeof(char) * (strlen(argv[1])
					 + strlen(INFILE_EXT) + 1));
    outfile_name = malloc(sizeof(char) * (strlen(argv[1])
					  + strlen(OUTFILE_EXT) + 1)); 
    if(infile_name == NULL || outfile_name == NULL)
      errmess(ERRMESS_NO_MEM);
    strcpy(infile_name, argv[1]);
    strcat(infile_name, INFILE_EXT);
    strcpy(outfile_name, argv[1]);
    strcat(outfile_name, OUTFILE_EXT);
  }

  /* Open files or quit */
  if((infile = fopen(infile_name, "r")) == NULL)
    errmess("Cannot open file");
  
  if((outfile = fopen(outfile_name, "w")) == NULL)
    errmess("Cannot open output file");

  /* Print message */
  printf("This is makeabbrev, version %s\n", version);
  printf("Scanning and sorting input file %s ...", infile_name);
  fflush(stdout);
  fprintf(outfile, "\\begin{theabbrev}\n");

  /* read every line */
  while(!feof(infile)) {
    line_num++;
    /* calculate line length - no limit on line lengths :-) */
    line_start = ftell(infile);
    while((i = fgetc(infile)) != EOF && i != '\n')
      ;
    line_end = ftell(infile);

    /* copy line to buffer */
    cptr = buffer = malloc(sizeof(char)*(line_end - line_start + 2));
    if(buffer == NULL) 
      errmess(ERRMESS_NO_MEM);
    fseek(infile, line_start, SEEK_SET);
    for(ell = line_start; ell < line_end -1; ++ell)
      *cptr++ = fgetc(infile);
    *cptr = '\0';
    fgetc(infile); /* ignore newline */
    abbrev_short = read_param(buffer, 1);
    abbrev_full = read_param(buffer, 2);
    if(abbrev_full == NULL || abbrev_short == NULL)
      continue; /* probably a blank line - ignore */
    key = read_param(buffer, 3);
        
    key_sanity_check(&key, abbrev_short);
    
    /* insert_node free()'s abbrev_short & abbrev_full if not
       inserted into list */
    insert_node(abbrev_short, abbrev_full, key);
          
    
    free(buffer);
  }

  printf("done\nGenerating output file %s ...", outfile_name);
  fflush(stdout);
  print_list(outfile);  
  fprintf(outfile, "\\end{theabbrev}\n");
  fclose(infile);
  fclose(outfile);
  printf("done\n");
  
  free(buffer);
  free(infile_name);
  free(outfile_name);
  
  return 0;
}


/** Read a LaTeX parameter (ie surronded by {}). The return string is
 *  created by malloc(), calling function to free() memory.
 *  @param str line of LaTeX text.
 *  @parameter_num number of parameter to find (starting at 1).
 *  @return The parameter value, without braces.
 */
char* read_param(const char *str, int parameter_num)
{
  int p_num = 0;
  int depth = 0;
  int p_len;
  char *p_str = NULL;
  const char *str_end = str + strlen(str) - 1;
  const char *cptr = str;
  const char *p_start = NULL;
  const char *p_end = NULL;

  while(p_end == NULL && cptr <= str_end) {
    switch(*cptr) {
    case '{':
      if((++depth) == 1)  
	if((++p_num) == parameter_num)  /* found start of a new parameter */
	  p_start = cptr + 1;
      break;

    case '}':
      if((--depth) == 0 && p_num == parameter_num) 
	p_end = cptr;
      break;
    }
    cptr++;
  }

  if(p_start && p_end) {
    p_len = (p_end - p_start);
    p_str = malloc(sizeof(char) * (p_len+1));
    if(p_str == NULL) 
      errmess(ERRMESS_NO_MEM);
    if(p_len)
      strncpy(p_str, p_start, p_len);
    p_str[p_len] = '\0';
  }
  return p_str; 
}


/** Sanity checking on key string. If key non-existent or whitespace
 *  then use the abbreviated form as the key.
 *  @param key_ptr The key, which may be modified in this function if
 *  necessary.
 *  @param abbrev_short The abbreviated form.
 */
void key_sanity_check(char **key_ptr, const char *abbrev_short)
{
  if(*key_ptr == NULL) {
    *key_ptr = malloc(sizeof(char) * (strlen(abbrev_short) + 1));
    if(*key_ptr == NULL)
      errmess(ERRMESS_NO_MEM);
    strcpy(*key_ptr, abbrev_short);
    /* strdup not POSIX
       key = strdup(abbrev_short);
    */
  }
  else {
    int i;
    int blank = 1;
    for(i = 0; i < strlen(*key_ptr); ++i)
	if(!isspace(*key_ptr[i])) {
	  blank = 0;
	  break;
	}
    if(blank) {
      free(*key_ptr);
      *key_ptr = malloc(sizeof(char) * (strlen(abbrev_short) + 1));
      if(*key_ptr == NULL)
	errmess(ERRMESS_NO_MEM);
      strcpy(*key_ptr, abbrev_short);
    }
  }

  return;  
}


/** Create a string containing the LaTeX \abbrevitem command, suitable
 *  for reading back in LaTeX when \printabbrev is called in
 *  LaTeX. The return string is created by malloc(), calling function
 *  to free() memory.
 *  @return string containing the \abbrevitem command;
 */
char* make_abbrevitem(const char* abbrev_short, const char* abbrev_full)
{
  const char* fmt_str = "\\abbrevitem{%s}{%s}\n";
  const int fmt_str_len = strlen(fmt_str) - strlen("%s%s");
  char* ret_str;

  ret_str = malloc(sizeof(char) * (fmt_str_len 
				   + strlen(abbrev_short) 
				   + strlen(abbrev_full) + 1));
  sprintf(ret_str, fmt_str, abbrev_short, abbrev_full);
  return ret_str;
}


/** Compare two nodes. Return string created by malloc(), calling
 *  function to free() memory.
 *  @param node 1 First node.
 *  @param node 2 Second node.
 *  @return n1 <  n2 : -1 <br>
 *          n1 == n2 :  0 <br>
 *          n1 > n2 : +1 <br> */
int nodecasecmp(const node *n1, const node *n2)
{
  int r;
  assert(n1);
  assert(n2);
  r = strcasecmp(n1->key, n2->key);
  if(r)
    return r;
  r = strcasecmp(n1->abbrev_short, n2->abbrev_short);
  if(r)
    return r;
  r = strcasecmp(n1->abbrev_full, n2->abbrev_full);
  return r;
}

/** Insert a node into the linked list. Insert (in increasing
 *  alphabetical order) only if abbrev is unique.
 *  @param abbrev_short The abbreviated form.
 *  @param abbrev_full The abbreviation written out in full.
 *  @param key The key to use for sorting the list.
 *  @return none 
 */
void insert_node(char *abbrev_short, char *abbrev_full, char *key)
{
  int cmp;
  node *new_node;
  node *current_node = list_start;
  node *previous_node = NULL;

  /* create new node */
  new_node = malloc(sizeof(node));
  if(new_node == NULL)
    errmess(ERRMESS_NO_MEM);
  
  new_node->abbrevitem = make_abbrevitem(abbrev_short, abbrev_full);
  new_node->key = key;
  new_node->abbrev_short = abbrev_short;
  new_node->abbrev_full = abbrev_full;

  /* Loop through term until insertion point found */
  
  while(current_node != NULL
	&& (cmp = nodecasecmp(new_node, current_node)) >= 0) {
    if(!cmp) {
      /* already exists in list */
      free_node(new_node);
      return;
    }

    /* go to next node */
    previous_node = current_node;
    current_node = current_node->next;
  }
  /* insert new node */
  new_node->next = current_node;
  if(previous_node == NULL) 
    list_start = new_node;
  else
    previous_node->next = new_node;
  
  return;
}


/** Print the osrted list.
 *  @param file file/stream to print to.
 */
void print_list(FILE *file)
{
  node *node_ptr = list_start;
  while(node_ptr != NULL) {
    fprintf(file, "%s", node_ptr->abbrevitem);
    node_ptr = node_ptr->next;
  }
  return;
}

/** Exit cleanly and with a meaningful error message.
 *  @param message Plain text error message.
 *  @return Never returns.
 */
void errmess(const char* message)
{
  printf("%s\n", message);
  exit(1);
}

/** Free the memory used by a node.
 *  @param n the node
 */
void free_node(node *n)
{
  free(n->abbrevitem);
  free(n->key);
  free(n->abbrev_short);
  free(n->abbrev_full);
  free(n);
  return;
}
    
