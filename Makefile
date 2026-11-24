include $(TOPDIR)/rules.mk

PKG_NAME:=nowhere
PKG_VERSION:=3.4.0
PKG_RELEASE:=1

PKG_SOURCE_SUBDIR:=Nowhere-$(PKG_VERSION)
PKG_SOURCE:=$(PKG_SOURCE_SUBDIR).tar.gz
PKG_SOURCE_URL:=https://codeload.github.com/NodePassProject/Nowhere/tar.gz/refs/tags/v$(PKG_VERSION)?
PKG_HASH:=e59aa7e83c9bd824bab45c6122e4ea941272f2f2c2a2de84ef9469feaf5fddf1
PKG_BUILD_DIR:=$(BUILD_DIR)/$(PKG_SOURCE_SUBDIR)

PKG_LICENSE:=GPL-3.0-only
PKG_LICENSE_FILES:=LICENSE
PKG_MAINTAINER:=NodePassProject
PKG_BUILD_DEPENDS:=rust/host
PKG_BUILD_PARALLEL:=1

include $(INCLUDE_DIR)/package.mk
include $(TOPDIR)/feeds/packages/lang/rust/rust-package.mk

define Package/nowhere
  SECTION:=net
  CATEGORY:=Network
  SUBMENU:=Web Servers/Proxies
  TITLE:=TLS and QUIC encrypted relay
  URL:=https://github.com/NodePassProject/Nowhere
  DEPENDS:=$(RUST_ARCH_DEPENDS) +ca-bundle
endef

define Package/nowhere/description
 Nowhere relays TCP and UDP over TLS or QUIC using the NW3 protocol.
 It provides Portal relay, Vector SOCKS5 ingress and remote TLS/QUIC Egress modes.
endef

define Package/nowhere/conffiles
/etc/config/nowhere
endef

define Package/nowhere/install
	$(INSTALL_DIR) $(1)/usr/bin
	$(INSTALL_BIN) $(PKG_INSTALL_DIR)/bin/nowhere $(1)/usr/bin/nowhere
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/nowhere.config $(1)/etc/config/nowhere
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/nowhere.init $(1)/etc/init.d/nowhere
endef

$(eval $(call RustBinPackage,nowhere))
$(eval $(call BuildPackage,nowhere))
