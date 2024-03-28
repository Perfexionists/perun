/* SPDX-License-Identifier: (LGPL-2.1 OR BSD-2-Clause)
   Copyright (c) 2023 Perun Team */

#pragma once

struct event {
	// [0]: 32 lowest bits: pid, 32 upper bits: func ID (28b) + event type (4b) 
	// [1]: 32 empty, 32b tid
	// [2]: 64b timestamp in ns
	uint64_t data[3];
};
