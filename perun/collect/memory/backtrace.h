#ifndef BACKTRACE_H
#define BACKTRACE_H

/** Function writes stack trace metadata into log file.
 * 
 *  @param log  File descriptor of the log file
 *  @param skip number of calls to omit in log
 */
void backtrace(FILE *log, unsigned skip);

#endif /* BACKTRACE_H */