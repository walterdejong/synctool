#!/usr/bin/perl
#
#>
# check_synctool.pl by Jurriaan Saathof <jurriaan@sara.nl>, 2012
#
# Nagios check to check the status of synctool
#>

use strict;
use warnings;

use lib '/usr/lib/nagios/plugins';
use utils qw(%ERRORS);

################################################################################
# Main
################################################################################

my $result = main();
exit($ERRORS{$result});

################################################################################
# Subroutines
################################################################################

sub main {

	my $status_ref = get_status();

	(my $result, my $message_ref, my $performancedata_ref) = process_status($status_ref);

	$"=", ";
	print "$result: @{$message_ref} | @{$performancedata_ref}\n";

	return($result);
}

sub get_status {

	my %status;

	my @regexlist;
	push(@regexlist, '(?<host>[a-z0-9\-]+): DRY RUN, not doing any updates');
	push(@regexlist, '(?<host>[a-z0-9\-]+): (?<file>[a-z0-9/_.\-]+) (?<status>mismatch|does not exist)( \([a-zA-Z ]+\))?');

	my $command = '/usr/bin/sudo /opt/synctool/sbin/synctool';

	open(INPUT, "$command|") || die "Unable to open $command: $!\n";

	while( my $line = <INPUT> ) {

		chomp($line);

		if( $line =~ /$regexlist[0]/ ) {

			$status{$+{host}} = {};
		}
		elsif( $line =~ /$regexlist[1]/ ) {

			$status{$+{host}} = {
				%{$status{$+{host}}},
				$+{file}	=> $+{status},
				}
		}
	}

	close(INPUT);

	return(\%status);
}

sub process_status {

	my $status_ref = shift;

	my $result = 'OK';
	my @message;
	my @performancedata;

	my @hosts;

	foreach my $host ( sort keys %{$status_ref} ) {

		my $count = keys(%{$status_ref->{$host}});

		if( $count ) {

			$result = 'WARNING';
			push(@hosts, $host);
		}

		push(@performancedata, "$host:".( $count==0 ? " no" : " $count" ).( $count==1 ? " file" : " files" ).( $count==0 ? " to" : " not in" )." sync");
	}

	# Check if there are hosts found which are not in sync
	if( $#hosts > -1 ) {

		push(@message, $#hosts+1 . ( $#hosts+1 == 1 ? " host" : " hosts" )." not in sync");
	}
	else {

		push(@message, "All hosts are in sync");
	}

	return($result, \@message, \@performancedata);
}
