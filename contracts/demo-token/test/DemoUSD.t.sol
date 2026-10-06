// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Test} from "forge-std/Test.sol";
import {DemoUSD} from "../src/DemoUSD.sol";

contract DemoUSDTest is Test {
    DemoUSD token;
    address owner = makeAddr("owner");
    address alice = makeAddr("alice");
    address bob = makeAddr("bob");

    event Transfer(address indexed from, address indexed to, uint256 value);

    function setUp() public {
        token = new DemoUSD(owner);
    }

    function test_metadata() public view {
        assertEq(token.name(), "Sendly Demo USD");
        assertEq(token.symbol(), "DemoUSD");
        assertEq(token.decimals(), 6);
        assertEq(token.owner(), owner);
    }

    function test_ownerMints() public {
        vm.prank(owner);
        token.mint(alice, 100e6);
        assertEq(token.balanceOf(alice), 100e6);
        assertEq(token.totalSupply(), 100e6);
    }

    function test_nonOwnerCannotMint() public {
        vm.expectRevert(DemoUSD.NotOwner.selector);
        vm.prank(alice);
        token.mint(alice, 1);
    }

    function test_transferEmitsEventSendlyVerifies() public {
        vm.prank(owner);
        token.mint(alice, 50e6);

        vm.expectEmit(true, true, false, true);
        emit Transfer(alice, bob, 15e6);
        vm.prank(alice);
        assertTrue(token.transfer(bob, 15e6));

        assertEq(token.balanceOf(alice), 35e6);
        assertEq(token.balanceOf(bob), 15e6);
    }

    function test_transferRevertsOnInsufficientBalance() public {
        vm.expectRevert(abi.encodeWithSelector(DemoUSD.InsufficientBalance.selector, 0, 1));
        vm.prank(alice);
        token.transfer(bob, 1);
    }

    function test_transferToZeroReverts() public {
        vm.prank(owner);
        token.mint(alice, 1);
        vm.expectRevert(DemoUSD.ZeroAddress.selector);
        vm.prank(alice);
        token.transfer(address(0), 1);
    }

    function test_transferFromUsesAllowance() public {
        vm.prank(owner);
        token.mint(alice, 10e6);
        vm.prank(alice);
        token.approve(bob, 4e6);

        vm.prank(bob);
        token.transferFrom(alice, bob, 3e6);
        assertEq(token.allowance(alice, bob), 1e6);

        vm.expectRevert(abi.encodeWithSelector(DemoUSD.InsufficientAllowance.selector, 1e6, 2e6));
        vm.prank(bob);
        token.transferFrom(alice, bob, 2e6);
    }

    function testFuzz_transferConservesSupply(uint96 minted, uint96 sent) public {
        vm.assume(sent <= minted);
        vm.prank(owner);
        token.mint(alice, minted);
        vm.prank(alice);
        token.transfer(bob, sent);
        assertEq(token.balanceOf(alice) + token.balanceOf(bob), token.totalSupply());
    }
}
