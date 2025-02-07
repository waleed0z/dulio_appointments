                    $divAppointmentContainer = $('#divAppointmentContainer'),
                    $divAppointmentDetailContainer = $('#divAppointmentDetailContainer'),
                    $divAppointmentContent = $('#divAppointmentContent'),
                    $spanAppointmentDateDetails = $('#spanAppointmentDateDetails'),
                    $spanPatientNameDetails = $('#spanPatientNameDetails'),
                    $spanProviderNameDetails = $('#spanProviderNameDetails'),
                    $spanAppointmentTypeDetails = $('#spanAppointmentTypeDetails'),
                    $spanAppointmentOrgDetails = $('#spanAppointmentOrgDetails'),
                    $spanAppointmentNoteDetails = $('#spanAppointmentNoteDetails'),
                    $tableAppointmentData = $('#tableAppointmentData'),
                    $iPrevPage = $('#iPrevPage'),
                    $iNextPage = $('#iNextPage'),
                    $tableHeader = $('#tableHeader'),
                    $tableBody = $('#tableAppointmentData tbody'),
                    $tableRows = $('tr', $tableBody),
                    $headerColumns = $('td', $tableHeader),
                    $selAppointmentFilter = $('#selAppointmentFilter'),
                    $spanCurrentPage = $('#spanCurrentPage'),
                    $spanTotalPages = $('#spanTotalPages'),
                    $upcomingRecords = $tableRows.filter(':not(.past-appointment-entry)').hide(),
                    $pastRecords = $tableRows.filter('.past-appointment-entry').hide(),
                    $divNoRecordsFound = $('#divNoRecordsFound');
                
                //FILTER
                $selAppointmentFilter.on('change', function() {
                    bindRecords();
                });
                
                //ROW SELECTIONS
                $tableRows.on('click', function() {
                    var $this = $(this);
                    if ($this.hasClass('selected-row')) return;
                
                    $tableRows.removeClass('selected-row');
                    $this.addClass('selected-row');
                
                    $divAppointmentDetailContainer.show();
                    $spanAppointmentDateDetails.text($this.attr('data-date'));
                    $spanPatientNameDetails.text($this.attr('data-client'));
                    $spanProviderNameDetails.text($this.attr('data-time'));
                    $spanAppointmentTypeDetails.text($this.attr('data-staff'));
                    $spanAppointmentOrgDetails.text($this.attr('data-mail'));
                    $spanAppointmentNoteDetails.text($this.attr('data-note'));
                    $divAppointmentContent.show();
                });
                
                //SORTING
                $headerColumns.on('click', function() {
                    var $this = $(this),
                            $iSortIcon = $('i', $this);
                
                    $headerColumns.filter(function() {
                        return (this !== $this[0]);
                    }).find('i').removeClass('fa-sort-desc fa-sort-asc fa-sort').addClass('fa-sort');
                
                    if ($iSortIcon.hasClass('fa-sort')) {
                        $iSortIcon.removeClass('fa-sort').addClass('fa-sort-desc');
                    } else if ($iSortIcon.hasClass('fa-sort-desc')) {
                        $iSortIcon.removeClass('fa-sort-desc').addClass('fa-sort-asc');
                    } else if ($iSortIcon.hasClass('fa-sort-asc')) {
                        $iSortIcon.removeClass('fa-sort-asc').addClass('fa-sort-desc');
                    }
                });
                
                // PAGINATION
                var totalRecordsPerPage = 6,
                        currentDate = new Date(),
                        currentYear = currentDate.getFullYear(),
                        targetRecords,
                        totalDisplayRecords,
                        totalPages;
                
                function daysBetweenDates(date1, date2) {
                  return Math.round(Math.abs(date1.getTime() - date2.getTime()) / (1000 * 60 * 60 * 24));
                };
                
                function bindRecords() {
                    var selectedFilter = $selAppointmentFilter.val(),
                            currentPage = $tableAppointmentData.attr('data-page');
                
                    targetRecords = (selectedFilter === 'upcoming' ? $upcomingRecords : $pastRecords);
                    totalDisplayRecords = targetRecords.length;
                    totalPages = Math.ceil(totalDisplayRecords / totalRecordsPerPage);
                    
                    $pastRecords.hide();
                    $upcomingRecords.hide();
                    $spanCurrentPage.text(currentPage);
                    $spanTotalPages.text(totalPages);
                    
                    for(var i = 0, x = 1, p = 1, addedRecords = 0, len = totalDisplayRecords; i < len; i++, x++) {
                        if (x === totalRecordsPerPage) {
                            p++;
                            x = 1;
                        }
                        var $row = $(targetRecords[i]);
                        $row.attr('data-page', p);
                        
                        if (selectedFilter === 'pastyear') {
                            var rowDate = new Date(Date.parse($row.attr('data-date'))),
                                betweenDays = daysBetweenDates(rowDate, currentDate);
                
                            if (betweenDays <= 365) {
                                $row.show();
                                addedRecords++;
                            }
                        } else if (selectedFilter === 'past3') {
                            var rowDate = new Date(Date.parse($row.attr('data-date'))),
                                    betweenDays = daysBetweenDates(rowDate, currentDate);
                            
                            if (betweenDays <= 90) {
                                $row.show();
                                addedRecords++;
                            }
                        } else if (i < totalRecordsPerPage) {
                            $row.show();
                            addedRecords++;
                        }
                    }
                    
                    if (parseInt(currentPage) === totalPages) {
                        $iNextPage.attr('disabled', 'disabled');
                        $iPrevPage.attr('disabled', 'disabled');
                    } else {
                        $iNextPage.removeAttr('disabled');
                    }
                    
                    if (addedRecords === 0) {
                        $divNoRecordsFound.show();
                        $tableAppointmentData.hide();
                        $divAppointmentDetailContainer.hide();
                    } else {
                        $divNoRecordsFound.hide();
                        $tableAppointmentData.show();
                        $divAppointmentDetailContainer.show();
                    }
                }
                $iNextPage.on('click', function() {
                    var currentPage = $tableAppointmentData.attr('data-page');
                    if (targetRecords != null && targetRecords.length > 0 && currentPage < totalPages) {
                        currentPage++;
                        targetRecords.filter('[data-page="' + (currentPage-1) + '"]').hide();
                        targetRecords.filter('[data-page="' + currentPage + '"]').show();
                        $tableAppointmentData.attr('data-page', currentPage);
                        $spanCurrentPage.text(currentPage);
                        $iPrevPage.removeAttr('disabled');
                        $divAppointmentDetailContainer.hide();
                    }
                    if ((currentPage+1) >= totalPages) {
                        $iNextPage.attr('disabled', 'disabled');
                    }
                });
                $iPrevPage.on('click', function() {
                    var currentPage = $tableAppointmentData.attr('data-page');
                    if (targetRecords != null && targetRecords.length > 0 && (currentPage-1 >= 1)) {
                        currentPage--;
                        targetRecords.filter('[data-page="' + (currentPage+1) + '"]').hide();
                        targetRecords.filter('[data-page="' + currentPage + '"]').show();
                        $tableAppointmentData.attr('data-page', currentPage);
                        $spanCurrentPage.text(currentPage);	
                        $iNextPage.removeAttr('disabled');
                        $divAppointmentDetailContainer.hide();
                    }
                    if ((currentPage-1) <= 0) {
                        $iPrevPage.attr('disabled', 'disabled');
                    }
                });
                
                bindRecords();
                
                setTimeout(function() {
                    if ($tableRows.length > 0) {
                        $tableRows[0].click();
                    }
                }, 800);