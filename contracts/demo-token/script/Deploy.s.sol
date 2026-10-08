// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Script, console} from "forge-std/Script.sol";
import {DemoUSD} from "../src/DemoUSD.sol";

/// Deploys DemoUSD with the broadcasting account as owner.
/// Usage (see README): forge script script/Deploy.s.sol --rpc-url monad_testnet --account <keystore> --broadcast
contract Deploy is Script {
    function run() external returns (DemoUSD token) {
        vm.startBroadcast();
        // msg.sender inside run() is Foundry's placeholder DEFAULT_SENDER, not the --account
        // wallet; read the actual broadcaster instead so the owner can mint.
        (, address broadcaster,) = vm.readCallers();
        require(broadcaster != DEFAULT_SENDER, "No broadcaster: pass --account or --private-key");
        token = new DemoUSD(broadcaster);
        vm.stopBroadcast();
        require(token.owner() == broadcaster, "Owner is not the broadcaster");
        console.log("DemoUSD deployed at", address(token));
        console.log("Owner", broadcaster);
    }
}
